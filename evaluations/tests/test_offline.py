"""Offline evaluation tests using scripted responses.

These tests verify the evaluation framework structure works correctly.
They do NOT test actual LLM quality -- they use canned responses.
LangSmith is disabled (see conftest.py).
"""

from __future__ import annotations

import pytest

from evaluations.evaluators import grade_task
from evaluations.runner import EvaluationRun, EvaluationRunner
from evaluations.tasks import EvaluationTask
from evaluations.tasks.task_001 import TASK_001
from evaluations.tasks.task_002 import TASK_002
from evaluations.tasks.task_004 import TASK_004
from evaluations.tasks.task_009 import TASK_009


# ---------------------------------------------------------------------------
# Grade function tests
# ---------------------------------------------------------------------------


def test_grade_task_passes_when_facts_found():
    task = EvaluationTask(
        task_id="TEST-001",
        question="How many buildings?",
        expected_tool="list_tables",
        expected_facts=["20"],
        description="test",
    )
    record = grade_task(
        task,
        answer="There are 20 buildings in the dataset.",
        tools_called=[{"tool": "list_tables", "args": {}}],
    )
    assert record.passed is True
    assert record.score == 1.0


def test_grade_task_fails_when_fact_missing():
    task = EvaluationTask(
        task_id="TEST-002",
        question="Which building?",
        expected_tool=None,
        expected_facts=["B007"],
        description="test",
    )
    record = grade_task(
        task,
        answer="Building B001 has the highest.",
        tools_called=[],
    )
    assert record.passed is False
    assert record.score == 0.0


def test_grade_task_checks_expected_tool():
    task = EvaluationTask(
        task_id="TEST-003",
        question="test",
        expected_tool="get_building_summary",
        expected_facts=[],
        description="test",
    )
    record = grade_task(
        task,
        answer="Some answer",
        tools_called=[{"tool": "run_readonly_query", "args": {}}],
    )
    assert record.passed is False


def test_grade_task_checks_expected_value():
    task = EvaluationTask(
        task_id="TEST-004",
        question="test",
        expected_tool=None,
        expected_facts=[],
        expected_value=55.0,
        expected_value_tolerance=5.0,
        description="test",
    )
    record = grade_task(
        task,
        answer="The increase was approximately 53%.",
        tools_called=[],
    )
    assert record.passed is True


def test_grade_task_value_check_fails_outside_tolerance():
    task = EvaluationTask(
        task_id="TEST-005",
        question="test",
        expected_tool=None,
        expected_facts=[],
        expected_value=55.0,
        expected_value_tolerance=2.0,
        description="test",
    )
    record = grade_task(
        task,
        answer="The increase was approximately 30%.",
        tools_called=[],
    )
    assert record.passed is False


# ---------------------------------------------------------------------------
# Runner tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_executes_task():
    """Test that the runner can execute a task with a scripted agent function."""

    async def fake_agent(question: str) -> tuple[str, list[dict[str, object]]]:
        return "There are 20 buildings.", [{"tool": "list_tables", "args": {}}]

    runner = EvaluationRunner(agent_run_fn=fake_agent)
    record = await runner.run_task(TASK_001)
    assert record.task_id == "TASK-001"
    assert record.passed is True


@pytest.mark.asyncio
async def test_runner_suite():
    """Test that the runner can execute a suite of tasks."""

    async def fake_agent(question: str) -> tuple[str, list[dict[str, object]]]:
        if "buildings" in question.lower():
            return "There are 20 buildings.", [{"tool": "list_tables", "args": {}}]
        return "I don't know.", []

    runner = EvaluationRunner(agent_run_fn=fake_agent)
    result = await runner.run_suite([TASK_001, TASK_002])
    assert isinstance(result, EvaluationRun)
    assert result.total == 2
    assert result.passed >= 1  # At least TASK_001 should pass


@pytest.mark.asyncio
async def test_task_009_records_correctly():
    """Offline: verify evaluation framework produces a correctly-structured record."""

    async def fake_agent(question: str) -> tuple[str, list[dict[str, object]]]:
        return (
            "Building B007 had a 55% increase from July to August 2024.",
            [{"tool": "get_consumption_trend", "args": {}}],
        )

    runner = EvaluationRunner(agent_run_fn=fake_agent)
    record = await runner.run_task(TASK_009)
    assert record.task_id == "TASK-009"
    assert record.final_answer != ""
    assert record.passed is True


@pytest.mark.asyncio
async def test_task_004_records_correctly():
    """Offline: verify TASK-004 can be graded."""

    async def fake_agent(question: str) -> tuple[str, list[dict[str, object]]]:
        return (
            "Building B007 had the largest increase.",
            [{"tool": "get_consumption_trend", "args": {}}],
        )

    runner = EvaluationRunner(agent_run_fn=fake_agent)
    record = await runner.run_task(TASK_004)
    assert record.task_id == "TASK-004"
    assert record.passed is True
