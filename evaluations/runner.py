"""Evaluation runner -- executes evaluation tasks against the agent.

Supports both offline (FakeChatModel) and online (real LLM) evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluations.evaluators import EvaluationRecord, grade_task
from evaluations.tasks import EvaluationTask


@dataclass
class EvaluationRun:
    """Results of running a suite of evaluation tasks."""

    records: list[EvaluationRecord] = field(default_factory=list)
    total: int = 0
    passed: int = 0

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


class EvaluationRunner:
    """Runs evaluation tasks against an agent service.

    Accepts a pre-configured agent_run_fn that takes a question and returns
    (answer, tools_called). This allows the runner to work with both
    real agent services and fake/scripted setups.
    """

    def __init__(
        self,
        agent_run_fn: Any,
    ) -> None:
        """Initialize the evaluation runner.

        Args:
            agent_run_fn: An async callable that takes a question string and
                         returns a tuple of (answer: str, tools_called: list[dict]).
        """
        self._agent_run_fn = agent_run_fn

    async def run_task(self, task: EvaluationTask) -> EvaluationRecord:
        """Run a single evaluation task and grade the result.

        Args:
            task: The evaluation task to run.

        Returns:
            EvaluationRecord with the graded result.
        """
        answer, tools_called = await self._agent_run_fn(task.question)
        return grade_task(task, answer, tools_called)

    async def run_suite(self, tasks: list[EvaluationTask]) -> EvaluationRun:
        """Run a suite of evaluation tasks.

        Args:
            tasks: List of evaluation tasks to execute.

        Returns:
            EvaluationRun with all records and aggregate scores.
        """
        run = EvaluationRun()
        for task in tasks:
            record = await self.run_task(task)
            run.records.append(record)
            run.total += 1
            if record.passed:
                run.passed += 1
        return run
