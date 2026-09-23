"""TASK-001: How many buildings are in the dataset?"""

from evaluations.tasks import EvaluationTask

TASK_001 = EvaluationTask(
    task_id="TASK-001",
    question="How many buildings are in the dataset?",
    expected_tool="list_tables",
    expected_facts=["20"],
    expected_value=20,
    expected_value_tolerance=0,
    description="Simple lookup: count of buildings in the dataset.",
)
