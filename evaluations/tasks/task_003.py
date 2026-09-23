"""TASK-003: B007 total electricity consumption in July 2024."""

from evaluations.tasks import EvaluationTask

TASK_003 = EvaluationTask(
    task_id="TASK-003",
    question="What was B007's total electricity consumption in July 2024?",
    expected_tool="get_building_summary",
    expected_facts=["B007", "July"],
    description="Lookup: specific building's consumption for a specific month.",
)
