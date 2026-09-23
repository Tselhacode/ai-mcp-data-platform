"""TASK-004: Largest increase from July to August 2024."""

from evaluations.tasks import EvaluationTask

TASK_004 = EvaluationTask(
    task_id="TASK-004",
    question="Which building had the largest increase from July to August 2024?",
    expected_tool="get_consumption_trend",
    expected_facts=["B007"],
    description="Trend: identify the building with largest July-to-August increase (B007, ~55%).",
)
