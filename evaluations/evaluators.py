"""Grading functions for evaluation tasks.

Evaluators check agent results against expected criteria.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluations.tasks import EvaluationTask


@dataclass
class EvaluationRecord:
    """Result of running a single evaluation task."""

    task_id: str
    question: str
    final_answer: str
    tools_called: list[dict[str, object]]
    passed: bool
    score: float
    reason: str


def grade_task(
    task: EvaluationTask,
    answer: str,
    tools_called: list[dict[str, object]],
) -> EvaluationRecord:
    """Grade an agent's response against a task's expected criteria.

    Checks:
    1. Expected facts appear in the answer
    2. Expected tool was called (if specified)
    3. Expected value is within tolerance (if specified)

    Args:
        task: The evaluation task definition.
        answer: The agent's final answer text.
        tools_called: List of tool call records from the agent.

    Returns:
        EvaluationRecord with pass/fail and scoring details.
    """
    reasons: list[str] = []
    checks_passed = 0
    total_checks = 0

    # Check expected facts
    if task.expected_facts:
        for fact in task.expected_facts:
            total_checks += 1
            if fact.lower() in answer.lower():
                checks_passed += 1
            else:
                reasons.append(f"Expected fact '{fact}' not found in answer")

    # Check expected tool was called
    if task.expected_tool:
        total_checks += 1
        tool_names = [tc.get("tool", "") for tc in tools_called]
        if task.expected_tool in tool_names:
            checks_passed += 1
        else:
            reasons.append(
                f"Expected tool '{task.expected_tool}' not called. "
                f"Tools called: {tool_names}"
            )

    # Check expected value
    if task.expected_value is not None:
        total_checks += 1
        # Try to find the value in the answer
        import re

        numbers = re.findall(r"[\d,]+\.?\d*", answer.replace(",", ""))
        found_match = False
        for num_str in numbers:
            try:
                num = float(num_str)
                if abs(num - task.expected_value) <= task.expected_value_tolerance:
                    found_match = True
                    break
            except ValueError:
                continue
        if found_match:
            checks_passed += 1
        else:
            reasons.append(
                f"Expected value {task.expected_value} "
                f"(+/-{task.expected_value_tolerance}) not found in answer"
            )

    # Calculate score
    if total_checks == 0:
        score = 1.0 if answer.strip() else 0.0
        passed = bool(answer.strip())
    else:
        score = checks_passed / total_checks
        passed = checks_passed == total_checks

    reason = "; ".join(reasons) if reasons else "All checks passed"

    return EvaluationRecord(
        task_id=task.task_id,
        question=task.question,
        final_answer=answer,
        tools_called=tools_called,
        passed=passed,
        score=score,
        reason=reason,
    )
