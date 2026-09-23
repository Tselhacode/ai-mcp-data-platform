# Evaluation Framework

---

## Overview

The evaluation system has two distinct layers. They serve different purposes and
must not be conflated.

```
Layer 1: Application and MCP Tests
    ├── Purpose: verify deterministic behavior (tools, DB, API, security)
    ├── Requires: no LLM, no LangSmith, no network
    ├── Runs: every PR in CI, on every code change
    └── Tool: pytest

Layer 2: Agent Evaluations
    ├── Purpose: measure LLM agent quality (tool selection, reasoning, answers)
    ├── Requires: real LLM (for meaningful results) or FakeChatModel (for structure)
    ├── Runs: manually, scheduled, or on model/prompt changes
    └── Tools: pytest + optional LangSmith
```

**Why two layers?** Unit tests verify that `get_monthly_summary` returns correct
SQL results. They cannot verify that the LLM will *choose* to call
`get_monthly_summary` for a given question, or that its final answer is correct.
That requires running the actual agent. These are different kinds of correctness.

---

## Layer 1: Application and MCP Tests

These are documented in [docs/testing.md](testing.md). They cover:

- MCP tool contracts (schema validation, input/output shape)
- Database query correctness
- Repository behavior
- API endpoint contracts
- SQL allowlist security rules
- Error handling paths

These tests run entirely without an LLM. They use `FakeChatModel` only where
the agent layer must be constructed (e.g. API integration tests). They do not
test whether the agent behaves well — only whether the infrastructure is correct.

---

## Layer 2: Agent Evaluations

### Purpose

Agent evaluations answer the question: "Does the LLM agent produce correct,
grounded, safe answers for our analytical tasks?"

### Task Definitions Live in the Repository

All evaluation tasks are defined in `evaluations/tasks/`. They are version-controlled
and reproducible without LangSmith access. LangSmith is additive — it adds
trace visibility and experiment tracking on top of the local baseline.

### Data Structures

```python
@dataclass
class EvaluationTask:
    task_id: str                         # e.g. "TASK-009"
    question: str                        # the natural-language question
    expected_tool: str | None            # primary tool that should be called
    expected_facts: list[str]            # substrings expected in the answer
    expected_value: float | None         # numeric value expected in answer
    expected_value_tolerance: float      # tolerance for numeric match (default 0.01)
    description: str                     # human-readable task description

@dataclass
class EvaluationRecord:
    task_id: str
    question: str
    final_answer: str
    tools_called: list[dict]             # {"tool": name, "args": dict}

    # Result
    passed: bool
    score: float                         # 0.0 – 1.0
    reason: str                          # why it passed or failed
```

**Scoring logic** (in `evaluations/evaluators.py`):
1. **Fact check:** each string in `expected_facts` must appear in the answer (case-insensitive)
2. **Tool check:** `expected_tool` must appear in the list of called tools
3. **Value check:** `expected_value` must appear in the answer within `±expected_value_tolerance`

All checks must pass for `passed=True`. The `score` is the fraction of checks passed.

---

## Task Categories

| Category | Description |
|---|---|
| `lookup` | Find a specific fact (e.g. highest consumption building) |
| `comparison` | Compare two or more entities |
| `trend` | Identify trends or changes over time |
| `anomaly` | Detect unusual patterns |
| `multi_step` | Requires multiple sequential tool calls |
| `safety` | Should refuse the request |

---

## Worked Example: July-to-August Percentage Increase (TASK-009)

This is the canonical multi-step evaluation example. It demonstrates the full
agent reasoning loop from question to graded answer.

**Task definition (`evaluations/tasks/task_009.py`):**

```python
TASK_009 = EvaluationTask(
    task_id="TASK-009",
    question="What percentage did B007's electricity consumption increase "
             "from July to August 2024?",
    expected_tool="get_consumption_trend",
    expected_facts=["B007", "55"],          # answer must mention building + ~55%
    expected_value=55.0,
    expected_value_tolerance=5.0,           # accept 50%–60%
    description="Trend: percentage increase calculation (~55%).",
)
```

**Expected agent behavior:**

```
Step 1 — Agent receives question:
    "What percentage did B007's electricity consumption increase
     from July to August 2024?"

Step 2 — Agent selects tool:
    Tool: get_consumption_trend
    Args: {
      "building_id": "B007",
      "start_date": "2024-07-01",
      "end_date": "2024-08-31",
      "granularity": "month",
      "reading_type": "electricity"
    }

Step 3 — Tool result returned:
    {
      "building_id": "B007",
      "granularity": "month",
      "reading_type": "electricity",
      "data_points": [
        { "period": "2024-07", "total_kwh": 9221.4, "average_kwh": 12.4, "data_points": 744 },
        { "period": "2024-08", "total_kwh": 14291.2, "average_kwh": 19.2, "data_points": 744 }
      ]
    }

Step 4 — Agent reasons over results:
    July: 9,221 kWh → August: 14,291 kWh
    Increase: (14,291 - 9,221) / 9,221 = 55.0%

Step 5 — Agent returns final answer:
    "Building B007's electricity consumption increased by approximately 55%
     from July 2024 (9,221 kWh) to August 2024 (14,291 kWh)."
```

**Resulting EvaluationRecord:**

```json
{
  "task_id": "TASK-009",
  "question": "What percentage did B007's electricity consumption increase from July to August 2024?",
  "final_answer": "Building B007's electricity consumption increased by approximately 55% ...",
  "tools_called": [
    {"tool": "get_consumption_trend", "args": {"building_id": "B007", ...}}
  ],
  "passed": true,
  "score": 1.0,
  "reason": "All checks passed"
}
```

**What this example demonstrates:**
- The agent cannot answer from general knowledge — it must call `get_consumption_trend`
- The tool returns real data from the seeded database (B007 = ~55% increase by design)
- The evaluator checks: (1) "B007" in answer, (2) "55" in answer, (3) tool was called, (4) numeric value within ±5%
- LangSmith (if enabled) captures the full trace: LLM reasoning, tool call, result

---

## Evaluation Tasks

Ten tasks cover the main analytical use cases. All use the seeded dataset
(20 buildings, ~614k readings, deterministic seed) so expected answers are fixed.

### TASK-001: Dataset Overview
- **Question:** "How many buildings are in the dataset?"
- **Expected tool:** `list_tables`
- **Expected facts:** `["20"]`
- **Seed answer:** 20 buildings

### TASK-002: Highest Consumer
- **Question:** "Which building had the highest electricity consumption?"
- **Expected tool:** `run_readonly_query`
- **Expected facts:** `["B007"]`
- **Seed answer:** B007 (Central Data Center) is the highest consumer by design

### TASK-003: Monthly Total
- **Question:** "What was B007's total electricity consumption in July 2024?"
- **Expected tool:** `get_building_summary`
- **Expected facts:** `["B007", "July"]`

### TASK-004: Largest Increase
- **Question:** "Which building had the largest increase from July to August 2024?"
- **Expected tool:** `get_consumption_trend`
- **Expected facts:** `["B007"]`
- **Seed answer:** B007 increases ~55% — planted deterministically in seed data

### TASK-005: Monthly Trend
- **Question:** "Show me monthly electricity consumption for B007 from January to June 2024."
- **Expected tool:** `get_consumption_trend`
- **Expected facts:** `["B007"]`

### TASK-006: Anomaly Detection
- **Question:** "Are there any anomalous readings in November 2024?"
- **Expected tool:** `run_readonly_query`
- **Expected facts:** `["B003"]`
- **Seed answer:** B003 has a 3× spike in November — planted deterministically

### TASK-007: Aggregation
- **Question:** "What was the average electricity consumption across all buildings in Q1 2024?"
- **Expected tool:** `run_readonly_query`
- **Expected facts:** `[]` (open-ended; checks tool was called)

### TASK-008: Two-Building Comparison
- **Question:** "Compare B001 and B007 electricity consumption in July 2024."
- **Expected tool:** `get_building_summary`
- **Expected facts:** `["B001", "B007"]`

### TASK-009: Percentage Increase (canonical example)
- **Question:** "What percentage did B007's electricity consumption increase from July to August 2024?"
- **Expected tool:** `get_consumption_trend`
- **Expected facts:** `["B007", "55"]`
- **Expected value:** 55.0 ± 5.0%
- See [worked example above](#worked-example-july-to-august-percentage-increase-task-009)

### TASK-010: Gas Meter Discovery
- **Question:** "List all buildings with gas readings."
- **Expected tool:** `run_readonly_query`
- **Expected facts:** `["B001"]`
- **Seed answer:** B001–B010 have gas meters (B011–B020 electricity only)

---

## Scoring

| Check type | Scoring method |
|---|---|
| Fact presence (`expected_facts`) | Automated substring match (case-insensitive) |
| Tool usage (`expected_tool`) | Automated: tool name must appear in `tools_called` |
| Numeric value (`expected_value`) | Automated: value within `±expected_value_tolerance` |

All checks must pass for `passed=True`. Score is `checks_passed / total_checks`.

Tasks with empty `expected_facts` and no `expected_value` pass if the answer is non-empty
and the expected tool was called — verifying the tool was selected without requiring a
specific numeric result.

---

## LangSmith Integration

When `LANGSMITH_TRACING=true`:

**During evaluation runs**, every agent invocation creates a LangSmith trace.
The `langsmith_run_id` is captured in `EvaluationRecord` for cross-referencing.

**Datasets:** Evaluation tasks can be uploaded to a LangSmith dataset. This enables
running evaluations directly from LangSmith UI without re-running the local runner.

**Experiment tracking:** Successive runs with different models or prompts are grouped
as LangSmith experiments. Score trends are visible across model versions.

**Without LangSmith:** The local JSONL output and pytest results are the ground truth.
LangSmith adds trace visualization and experiment UI on top — it does not replace
the local record.

---

## Output

Results are stored as:

1. **JSONL file** (always) — `data/evals/<run_id>.jsonl`, one record per line
2. **Database record** (always) — `evaluation_runs` + `evaluation_records` tables
3. **LangSmith experiment** (if enabled) — linked via `langsmith_run_id`
4. **Summary report** — printed to stdout after each run

---

## Running Evaluations

```bash
# Offline — uses FakeChatModel, verifies framework structure (CI-safe)
cd evaluations && pytest

# Online — uses real Bedrock, local JSONL output (requires AWS credentials)
LLM_PROVIDER=bedrock python -m evaluations.runner --suite full

# Online with LangSmith tracing
LLM_PROVIDER=bedrock \
LANGSMITH_TRACING=true \
LANGSMITH_API_KEY=lsv2_... \
  python -m evaluations.runner --suite full

# Single task
python -m evaluations.runner --task TASK-009

# View last run
python -m evaluations.report --last
```

---

## Adding a New Evaluation Task

1. Add a `EvaluationTask` in `evaluations/tasks/your_task.py`
2. Verify the expected answer against seed data (`scripts/verify_task.py`)
3. If LLM judge: add judge prompt in `evaluations/judges/`
4. Add an offline test in `evaluations/tests/` using `FakeChatModel` to verify:
   - The task runs without error
   - `EvaluationRecord` is created with the correct structure
   - Scoring logic produces the right pass/fail result
5. Update this document
