"""Evaluation task definitions.

Each task is an EvaluationTask dataclass defining a question,
expected tool usage, and expected answer criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvaluationTask:
    """Definition of a single evaluation task."""

    task_id: str
    question: str
    expected_tool: str | None
    expected_facts: list[str] = field(default_factory=list)
    expected_value: float | None = None
    expected_value_tolerance: float = 0.01
    description: str = ""
