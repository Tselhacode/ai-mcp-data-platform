"""Evaluation report CLI.

Runs the evaluation task suite and produces a human-readable summary
plus optional JSON output.

Two modes:

  offline (default)
    Uses scripted "ideal" responses to verify the evaluation framework
    runs cleanly against all 10 task definitions. No LLM required.
    All tasks should pass in this mode.

  online (--online)
    Calls the running backend API at BACKEND_URL for each task.
    Requires a running server with a real LLM (LLM_PROVIDER=bedrock).
    Never required for CI.

Usage (from repo root):

    cd backend
    uv run python ../evaluations/report.py
    uv run python ../evaluations/report.py --output results.json
    uv run python ../evaluations/report.py --online --backend-url http://localhost:8000

The offline report demonstrates the evaluation framework.
The online report measures real LLM agent quality.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Evaluation imports — no LangChain, no FastAPI
from evaluations.evaluators import EvaluationRecord, grade_task
from evaluations.runner import EvaluationRun, EvaluationRunner
from evaluations.tasks import EvaluationTask
from evaluations.tasks.task_001 import TASK_001
from evaluations.tasks.task_002 import TASK_002
from evaluations.tasks.task_003 import TASK_003
from evaluations.tasks.task_004 import TASK_004
from evaluations.tasks.task_005 import TASK_005
from evaluations.tasks.task_006 import TASK_006
from evaluations.tasks.task_007 import TASK_007
from evaluations.tasks.task_008 import TASK_008
from evaluations.tasks.task_009 import TASK_009
from evaluations.tasks.task_010 import TASK_010

ALL_TASKS: list[EvaluationTask] = [
    TASK_001,
    TASK_002,
    TASK_003,
    TASK_004,
    TASK_005,
    TASK_006,
    TASK_007,
    TASK_008,
    TASK_009,
    TASK_010,
]

# ---------------------------------------------------------------------------
# Offline agent — returns the ideal scripted answer for each task
# ---------------------------------------------------------------------------

_OFFLINE_ANSWERS: dict[str, tuple[str, list[dict[str, object]]]] = {
    "TASK-001": (
        "There are 20 buildings in the dataset.",
        [{"tool": "list_tables", "args": {}}],
    ),
    "TASK-002": (
        "Building B007 had the highest electricity consumption.",
        [{"tool": "run_readonly_query", "args": {}}],
    ),
    "TASK-003": (
        "B007's total electricity consumption in July 2024 was approximately 23,808 kWh.",
        [{"tool": "get_building_summary", "args": {}}],
    ),
    "TASK-004": (
        "Building B007 had the largest increase from July to August 2024.",
        [{"tool": "get_consumption_trend", "args": {}}],
    ),
    "TASK-005": (
        "B007's monthly electricity trend from January to June 2024 shows: "
        "Jan 23,808 kWh, Feb 21,600 kWh, Mar 23,808 kWh, "
        "Apr 23,040 kWh, May 23,808 kWh, Jun 23,040 kWh.",
        [{"tool": "get_consumption_trend", "args": {}}],
    ),
    "TASK-006": (
        "Building B003 had anomalous electricity readings in November 2024.",
        [{"tool": "run_readonly_query", "args": {}}],
    ),
    "TASK-007": (
        "The average Q1 2024 electricity consumption across all buildings "
        "was approximately 15,000 kWh.",
        [{"tool": "run_readonly_query", "args": {}}],
    ),
    "TASK-008": (
        "In July 2024, B001 consumed 15,120 kWh and B007 consumed 23,808 kWh. "
        "B007 used significantly more electricity.",
        [{"tool": "get_building_summary", "args": {}}],
    ),
    "TASK-009": (
        "B007's electricity consumption increased by approximately 55% from July to August 2024.",
        [{"tool": "get_consumption_trend", "args": {}}],
    ),
    "TASK-010": (
        "Buildings with gas readings include B001 and others in the B001-B010 range.",
        [{"tool": "run_readonly_query", "args": {}}],
    ),
}


async def _offline_agent(question: str) -> tuple[str, list[dict[str, object]]]:
    """Return a scripted ideal answer matching expected task criteria."""
    for task in ALL_TASKS:
        if task.question == question:
            return _OFFLINE_ANSWERS.get(task.task_id, ("No scripted answer.", []))
    return ("No scripted answer.", [])


# ---------------------------------------------------------------------------
# Online agent — calls the running backend API
# ---------------------------------------------------------------------------


async def _online_agent(
    question: str, backend_url: str, session_id: str | None = None
) -> tuple[str, list[dict[str, object]]]:
    """Call the running backend API and return the agent's answer."""
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx is required for online mode. Install with: uv add httpx", file=sys.stderr)
        sys.exit(1)

    payload: dict[str, object] = {"question": question}
    if session_id:
        payload["session_id"] = session_id

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{backend_url}/api/v1/query", json=payload)
        response.raise_for_status()
        data = response.json()

    answer = data.get("answer", "")
    tools_used = [
        {"tool": t["tool"], "args": t.get("args", {})}
        for t in data.get("tools_used", [])
    ]
    return answer, tools_used


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

_WIDTH = 90
_COL_TASK = 10
_COL_STATUS = 8
_COL_SCORE = 7
_COL_QUESTION = 45
_COL_REASON = 20


def _render_text_report(run: EvaluationRun, mode: str, backend_url: str | None) -> str:
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append("=" * _WIDTH)
    lines.append("  AI MCP Data Platform — Evaluation Report")
    lines.append(f"  Generated: {now}")
    lines.append(f"  Mode:      {mode}" + (f"  ({backend_url})" if backend_url else ""))
    lines.append("=" * _WIDTH)
    lines.append("")

    if mode == "offline":
        lines.append(
            "  NOTE: Offline mode uses scripted ideal responses to verify the evaluation"
        )
        lines.append(
            "  framework structure. It does NOT measure real LLM agent quality."
        )
        lines.append(
            "  Use --online with a running backend to evaluate actual agent behaviour."
        )
        lines.append("")

    header = (
        f"  {'Task':<{_COL_TASK}}"
        f"{'Status':<{_COL_STATUS}}"
        f"{'Score':<{_COL_SCORE}}"
        f"{'Question':<{_COL_QUESTION}}"
    )
    lines.append(header)
    lines.append("  " + "-" * (_WIDTH - 2))

    for record in run.records:
        status = "PASS" if record.passed else "FAIL"
        question_preview = record.question[:_COL_QUESTION - 3] + "…" if len(record.question) > _COL_QUESTION - 3 else record.question
        row = (
            f"  {record.task_id:<{_COL_TASK}}"
            f"{status:<{_COL_STATUS}}"
            f"{record.score:<{_COL_SCORE}.2f}"
            f"{question_preview}"
        )
        lines.append(row)
        if not record.passed:
            lines.append(f"  {'':>{_COL_TASK + _COL_STATUS + _COL_SCORE}}↳ {record.reason}")

    lines.append("  " + "-" * (_WIDTH - 2))
    lines.append(
        f"  Result: {run.passed}/{run.total} tasks passed  "
        f"({run.score * 100:.1f}%)"
    )
    lines.append("=" * _WIDTH)
    return "\n".join(lines)


def _render_json_report(run: EvaluationRun, mode: str, backend_url: str | None) -> str:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "backend_url": backend_url,
        "summary": {
            "total": run.total,
            "passed": run.passed,
            "failed": run.total - run.passed,
            "score": round(run.score, 4),
        },
        "tasks": [
            {
                "task_id": r.task_id,
                "question": r.question,
                "passed": r.passed,
                "score": round(r.score, 4),
                "reason": r.reason,
                "final_answer": r.final_answer,
                "tools_called": r.tools_called,
            }
            for r in run.records
        ],
    }
    return json.dumps(report, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> None:
    mode = "online" if args.online else "offline"

    if mode == "online":
        backend_url = args.backend_url
        print(f"Running online evaluation against {backend_url} …", file=sys.stderr)

        async def agent_fn(question: str) -> tuple[str, list[dict[str, object]]]:
            return await _online_agent(question, backend_url)
    else:
        backend_url = None
        print("Running offline evaluation (scripted responses) …", file=sys.stderr)

        async def agent_fn(question: str) -> tuple[str, list[dict[str, object]]]:
            return await _offline_agent(question)

    runner = EvaluationRunner(agent_run_fn=agent_fn)
    run = await runner.run_suite(ALL_TASKS)

    if args.format == "json":
        output = _render_json_report(run, mode, backend_url)
    else:
        output = _render_text_report(run, mode, backend_url)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Exit 1 if any tasks failed (useful for scripting)
    if run.passed < run.total:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the evaluation suite and produce a report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Offline framework verification (no LLM required)
  cd backend && uv run python ../evaluations/report.py

  # JSON output
  cd backend && uv run python ../evaluations/report.py --format json --output results.json

  # Online evaluation (requires running backend with real LLM)
  cd backend && uv run python ../evaluations/report.py --online --backend-url http://localhost:8000
""",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Call running backend API instead of using scripted offline responses.",
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend API base URL for online mode (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (default) or json.",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write report to FILE instead of stdout.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
