"""TASK-005: Monthly electricity consumption for B007 from Jan-Jun 2024."""

from evaluations.tasks import EvaluationTask

TASK_005 = EvaluationTask(
    task_id="TASK-005",
    question="Show me monthly electricity consumption for B007 from January to June 2024.",
    expected_tool="get_consumption_trend",
    expected_facts=["B007"],
    description="Trend: multi-month consumption trend for a single building.",
)
