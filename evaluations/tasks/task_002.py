"""TASK-002: Which building had the highest electricity consumption?"""

from evaluations.tasks import EvaluationTask

TASK_002 = EvaluationTask(
    task_id="TASK-002",
    question="Which building had the highest electricity consumption?",
    expected_tool="run_readonly_query",
    expected_facts=["B007"],
    description="Lookup: identify the highest electricity consumer (B007).",
)
