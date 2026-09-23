"""TASK-006: Anomalous readings in November 2024."""

from evaluations.tasks import EvaluationTask

TASK_006 = EvaluationTask(
    task_id="TASK-006",
    question="Are there any anomalous readings in November 2024?",
    expected_tool="run_readonly_query",
    expected_facts=["B003"],
    description="Anomaly detection: B003 has a 3x spike in November 2024.",
)
