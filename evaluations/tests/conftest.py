"""Evaluation test fixtures.

CRITICAL: LangSmith must be disabled for all tests.
"""

import os

os.environ["LANGSMITH_TRACING"] = "false"
