"""TASK-009: Percentage increase in B007 electricity from July to August 2024."""

from evaluations.tasks import EvaluationTask

TASK_009 = EvaluationTask(
    task_id="TASK-009",
    question=(
        "What percentage did B007's electricity consumption increase "
        "from July to August 2024?"
    ),
    expected_tool="get_consumption_trend",
    expected_facts=["B007", "55"],
    expected_value=55.0,
    expected_value_tolerance=5.0,
    description="Trend: percentage increase calculation (~55%).",
)
