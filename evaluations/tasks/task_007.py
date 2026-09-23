"""TASK-007: Average electricity consumption across all buildings in Q1 2024."""

from evaluations.tasks import EvaluationTask

TASK_007 = EvaluationTask(
    task_id="TASK-007",
    question="What was the average electricity consumption across all buildings in Q1 2024?",
    expected_tool="run_readonly_query",
    expected_facts=[],
    description="Aggregation: average consumption across all buildings for a quarter.",
)
