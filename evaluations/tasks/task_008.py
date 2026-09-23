"""TASK-008: Compare B001 and B007 electricity consumption in July 2024."""

from evaluations.tasks import EvaluationTask

TASK_008 = EvaluationTask(
    task_id="TASK-008",
    question="Compare B001 and B007 electricity consumption in July 2024.",
    expected_tool="get_building_summary",
    expected_facts=["B001", "B007"],
    description="Comparison: two buildings side-by-side for one month.",
)
