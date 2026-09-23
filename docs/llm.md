# LLM and Agent Integration

---

## Overview

The LLM and agent layer uses **LangChain** for agent orchestration and **AWS Bedrock**
as the initial production LLM provider, accessed via `langchain-aws`.

The design keeps provider-specific code isolated to a single factory module so
the rest of the application is unaware of which LLM provider is active. All
automated tests use a `FakeChatModel` that makes no network calls.

**LangSmith** is optionally layered on top to provide trace visibility, evaluation
datasets, and experiment tracking. The application functions fully without it.

---

## Why LangChain

LangChain is used for agent orchestration, not as a general-purpose framework for
the entire application.

Specifically, LangChain provides:
1. **A tool-calling agent loop** — manages the cycle of LLM invocation → tool call →
   result → next LLM call, including multi-step sequences
2. **LangChain MCP adapter** — loads FastMCP tools as `BaseTool` instances so the
   agent can invoke them natively
3. **`BaseChatModel` abstraction** — a well-established interface for chat models
   that works across providers (Bedrock, OpenAI, Anthropic direct, Ollama, etc.)
4. **LangSmith integration** — zero-configuration tracing of every LLM call and
   tool invocation when LangSmith env vars are set

LangChain is NOT used for:
- Database access
- Business logic
- Application services
- Persistence
- MCP server implementation

---

## Model Abstraction

### The boundary

```
backend/llm/factory.py          ← only file that imports provider-specific packages
        │
        │  returns BaseChatModel
        ▼
AgentService(llm: BaseChatModel)  ← uses only langchain_core types
        │
        ▼
LangChain agent                   ← uses only langchain_core types
```

`backend/services/`, `backend/mcp/`, and `backend/data/` never import
`langchain_aws`, `boto3`, or any LLM provider SDK. They depend only on
`langchain_core.language_models.base.BaseChatModel`, which is the stable,
provider-agnostic interface.

### Factory

```python
# backend/llm/factory.py
from langchain_core.language_models.base import BaseChatModel
from app.config import Settings

def create_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "bedrock":
        from langchain_aws import ChatBedrock
        return ChatBedrock(
            model_id=settings.llm_model,
            region_name=settings.aws_region,
            # boto3 session uses standard credential chain — no hard-coded keys
        )
    elif settings.llm_provider == "fake":
        from backend.llm.fake import FakeChatModel
        return FakeChatModel()
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
```

---

## Production Provider: ChatBedrock (AWS Bedrock)

Uses the AWS Bedrock Converse API via `langchain-aws`, which supports tool use
across Claude 3 models.

**Environment variables:**
```bash
LLM_PROVIDER=bedrock
LLM_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_REGION=us-east-1
# AWS credentials from standard boto3 chain: IAM role > env vars > ~/.aws/credentials
# Never hard-code AWS credentials.
```

**In production (ECS):** IAM task role provides credentials automatically.
**Locally with Bedrock:** Use `aws sso login` or set `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`.

---

## Test Provider: FakeChatModel

Used in all automated tests. Makes no network calls, is fully deterministic,
and supports scripted tool-use responses.

```python
# backend/llm/fake.py
from langchain_core.language_models.base import BaseChatModel
from langchain_core.messages import AIMessage, ToolCall

@dataclass
class ScriptedResponse:
    """One scripted LLM response in a multi-turn conversation."""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    # If set, assert the incoming message contains this substring
    assert_input_contains: str | None = None

class FakeChatModel(BaseChatModel):
    """
    Deterministic fake LangChain chat model for testing.

    Replays a scripted list of responses in order. Raises AssertionError
    if assert_input_contains does not match the actual input — catching
    test fixture errors early.
    """
    script: list[ScriptedResponse]
    _call_count: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        response = self.script[self._call_count]
        self._call_count += 1
        if response.assert_input_contains:
            content = str(messages[-1].content)
            assert response.assert_input_contains in content
        if response.tool_calls:
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(
                    content="",
                    tool_calls=response.tool_calls,
                ))
            ])
        return ChatResult(generations=[
            ChatGeneration(message=AIMessage(content=response.content or ""))
        ])
```

**Example usage in a test:**

```python
from backend.llm.fake import FakeChatModel, ScriptedResponse
from langchain_core.messages import ToolCall

fake_llm = FakeChatModel(script=[
    # First turn: LLM calls a tool
    ScriptedResponse(
        assert_input_contains="highest consumption",
        tool_calls=[ToolCall(
            name="get_monthly_summary",
            args={"start_year_month": "2024-07", "end_year_month": "2024-08"},
            id="call_1",
        )],
    ),
    # Second turn: LLM produces final answer after seeing tool result
    ScriptedResponse(
        content="Building B007 had the highest increase, from 9,200 kWh in July "
                "to 14,291 kWh in August — a 55% increase.",
    ),
])
```

---

## Agent Orchestration

The LangChain agent lives in `backend/agent/`, not in `backend/services/`.
Application services (`backend/services/`) have no LangChain dependency.

```
backend/agent/
    agent_service.py  — public entry point; manages sessions; calls AnalystAgent
    analyst_agent.py  — constructs and invokes the LangGraph agent
    mcp_client.py     — loads FastMCP tools as LangChain BaseTool instances
    schemas.py        — AgentResult, ToolUsage (no LangChain types exposed)
```

**Implementation:**

```python
# backend/agent/analyst_agent.py
from langgraph.prebuilt import create_react_agent

class AnalystAgent:
    """Wraps LangGraph create_react_agent for energy analytics."""

    def __init__(self, llm: BaseChatModel, tools: Sequence[BaseTool],
                 max_iterations: int = 10) -> None:
        self._agent = create_react_agent(llm, tools, prompt=_SYSTEM_PROMPT)
        self._max_iterations = max_iterations

    async def invoke(self, question: str, history: list | None = None) -> AgentResult:
        result = await self._agent.ainvoke(
            {"messages": messages},
            config={"recursion_limit": self._max_iterations * 2 + 1},
        )
        ...
```

**Implementation choice: LangGraph `create_react_agent`.**
Uses `langgraph.prebuilt.create_react_agent` which provides a ReAct
tool-calling loop. Chosen over `AgentExecutor` because LangGraph offers
better control over iteration limits via `recursion_limit` and produces a
structured message history that makes tool usage extraction straightforward.

**Note:** `create_react_agent` is being moved to `langchain.agents` in
LangGraph V2.0. The current import path (`langgraph.prebuilt`) is deprecated
but functional. This is a known limitation — migration requires a one-line
import change.

**Max iterations:** Configured via `LLM_MAX_ITERATIONS` (default: 10).
Enforced via `config={"recursion_limit": max_iterations * 2 + 1}`.

---

## MCP Tools as LangChain Tools

The FastMCP server exposes tools via the MCP protocol. At application startup,
`backend/agent/mcp_client.py` connects to the server in-process and loads tools as
`StructuredTool` instances that the LangChain agent can invoke.

```python
# backend/agent/mcp_client.py

async def load_mcp_tools(mcp_server: FastMCP) -> list[StructuredTool]:
    """Load tools from a FastMCP server as LangChain StructuredTool instances."""
    async with FastMCPClient(mcp_server) as client:
        mcp_tools = await client.list_tools()
        for mcp_tool in mcp_tools:
            lc_tool = StructuredTool.from_function(
                coroutine=_make_tool_fn(mcp_tool.name),
                name=mcp_tool.name,
                description=mcp_tool.description,
            )
            tools.append(lc_tool)
    return tools
```

**Adapter note:** `langchain-mcp-adapters` v0.3.1 is incompatible with the
MCP SDK 2.2.0 installed by FastMCP 4.0.5. The custom adapter in
`mcp_client.py` uses `fastmcp.Client` directly as a workaround.

**The FastMCP server remains independently usable.** Any MCP-compatible client
(Claude Desktop, another framework, a test script) can connect to it. LangChain
is one client — it does not own or define the server.

---

## LangSmith Integration

### How it works

LangSmith tracing is automatic for LangChain code when configured:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=ai-mcp-data-platform
```

When these are set, the LangSmith SDK intercepts every LangChain call and sends
trace data (LLM calls, tool invocations, chain steps, latency, tokens) to LangSmith.
No application code changes are required.

### What LangSmith captures

For every agent invocation:
- Full execution tree (LLM calls, tool calls, their order)
- Token counts and latency for each LLM call
- Tool name, input, output for each tool invocation
- Final answer
- Run ID (stored in `EvaluationRecord.langsmith_run_id` for traceability)

### When disabled

When `LANGSMITH_TRACING=false` or env vars are absent:
- Zero network calls to LangSmith
- Application behavior is unchanged
- Local structured JSON logging captures the same events independently
- All automated tests pass without LangSmith credentials

**Tests always run with LangSmith disabled.** The `conftest.py` sets
`LANGSMITH_TRACING=false` unconditionally for all test runs.

### LangSmith for evaluations

In agent evaluation runs, LangSmith can:
- Store the evaluation dataset (task inputs + expected outputs)
- Run evaluators against recorded traces
- Track results across experiment runs (model versions, prompt changes)

This is in addition to the local JSONL output, which always runs regardless of
LangSmith availability. See [docs/evaluations.md](evaluations.md).

---

## How to Replace LangChain

If LangChain were to be removed:

1. **`backend/agent/`** — `AnalystAgent` and `mcp_tools.py` need new implementations
2. **`backend/llm/factory.py`** — needs to construct the new framework's model object
3. **`FakeChatModel`** — replaced with a new fake for the replacement framework

**Not affected (zero LangChain dependency):**
- Application services (`backend/services/`)
- Repositories (`backend/data/`)
- FastMCP server (`backend/mcp/`)
- API routes (`backend/app/`)
- Database schema
- Evaluation task definitions
- `AgentService` public interface (callers of `AgentService.run()` are unchanged)

The service and data layers have no LangChain dependency. This is the key
architectural guarantee.

---

## How to Add a New LLM Provider

1. Add the provider's LangChain package to `pyproject.toml`
   (e.g. `langchain-openai` for OpenAI)
2. Add a new branch in `backend/llm/factory.py`
3. Add `LLM_PROVIDER=openai` to the configuration documentation
4. Test with existing `FakeChatModel` tests (interface is the same)
5. Update this document

No changes to services, MCP tools, or API routes are required.

---

## Cost Considerations

Model provider costs (Bedrock, OpenAI, etc.) are separate from LangSmith costs.

| Scenario | LLM API cost | LangSmith cost |
|---|---|---|
| Unit tests (FakeChatModel) | $0 | $0 |
| Integration tests (FakeChatModel) | $0 | $0 |
| Offline evaluation tests (FakeChatModel) | $0 | $0 |
| Online evaluation run (real Bedrock) | Per token | Optional |
| Production traffic | Per token | Per trace (free tier available) |

Development and CI should never incur LLM API costs. Only intentional online
evaluation runs and production use incur model costs.

`LLM_MAX_TOKENS` (default: 4096) and `LLM_MAX_ITERATIONS` (default: 10) bound
the cost of any single agent invocation.
