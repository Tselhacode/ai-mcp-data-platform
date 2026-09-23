#!/usr/bin/env python3
"""Architecture boundary checker.

Enforces that LangChain/LangSmith/FastMCP cannot be imported in the wrong layers.
Run from the backend/ directory:
    python ../scripts/check_architecture.py
"""
import pathlib
import re
import sys

VIOLATIONS: list[str] = []

FORBIDDEN_IMPORTS: dict[str, list[str]] = {
    "services": ["langchain", "langsmith", "fastmcp"],
    "data": ["langchain", "langsmith", "fastmcp"],
    "mcp": ["langchain", "langsmith"],
    "app": ["langchain_aws", "langchain_core", "langgraph", "langsmith"],
}

# Only llm/factory.py may import langchain_aws
FACTORY_ONLY = ["langchain_aws", "ChatBedrock"]

backend = pathlib.Path(".")  # run from backend/

for layer, forbidden in FORBIDDEN_IMPORTS.items():
    layer_path = backend / layer
    if not layer_path.exists():
        continue
    for py_file in layer_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text()
        for pkg in forbidden:
            # Check for actual imports, not just mentions in comments
            if re.search(
                rf"^(from|import)\s+{re.escape(pkg)}", content, re.MULTILINE
            ):
                VIOLATIONS.append(
                    f"VIOLATION: {py_file} imports {pkg!r} (layer: {layer})"
                )

# Check factory-only
for py_file in backend.rglob("*.py"):
    if "__pycache__" in str(py_file) or ".venv" in str(py_file):
        continue
    if "llm/factory.py" in str(py_file):
        continue
    content = py_file.read_text()
    for pkg in FACTORY_ONLY:
        if re.search(
            rf"^(from|import)\s+{re.escape(pkg)}", content, re.MULTILINE
        ):
            VIOLATIONS.append(
                f"VIOLATION: {py_file} imports {pkg!r} (only allowed in llm/factory.py)"
            )

if VIOLATIONS:
    print("\n".join(VIOLATIONS))
    sys.exit(1)
else:
    print("Architecture boundary check: PASSED")
