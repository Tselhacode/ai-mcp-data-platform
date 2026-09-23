"""TASK-010: List all buildings with gas readings."""

from evaluations.tasks import EvaluationTask

TASK_010 = EvaluationTask(
    task_id="TASK-010",
    question="List all buildings with gas readings.",
    expected_tool="run_readonly_query",
    expected_facts=["B001"],
    description="Lookup: discover which buildings have gas meter data (B001-B010).",
)
