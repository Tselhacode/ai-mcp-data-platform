#!/usr/bin/env python3
"""Secret detection script.

Checks for common secret patterns in the repository.
"""
import pathlib
import re
import sys

SECRET_PATTERNS = [
    # AWS access key IDs begin with AKIA (long-term) or ASIA (temporary)
    (r"(?:AKIA|ASIA)[0-9A-Z]{16}", "AWS Access Key ID"),
    (
        r'(?i)aws_secret_access_key\s*=\s*["\'][^"\']{20,}["\']',
        "AWS Secret Key",
    ),
    # LangSmith keys: legacy ls-... and current lsv2_... format
    (
        r"(?i)LANGSMITH_API_KEY\s*=\s*(?:ls-|lsv2_)[a-zA-Z0-9_\-]{20,}",
        "LangSmith API Key (real)",
    ),
    # OpenAI-style keys
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI-style API Key"),
    # Anthropic API keys
    (r"sk-ant-[a-zA-Z0-9\-]{30,}", "Anthropic API Key"),
    (
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        "Private Key",
    ),
    (r'(?i)password\s*=\s*["\'][^"\']{8,}["\']', "Password in code"),
]

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".claude",
}
SKIP_EXTENSIONS = {
    ".pyc",
    ".png",
    ".jpg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".lock",
}
SKIP_FILES = {".env.example", "check_secrets.py"}

violations: list[str] = []
repo_root = pathlib.Path(".")

for path in repo_root.rglob("*"):
    if path.is_dir():
        continue
    if any(skip in path.parts for skip in SKIP_DIRS):
        continue
    if path.suffix in SKIP_EXTENSIONS:
        continue
    if path.name in SKIP_FILES:
        continue
    if path.name.startswith(".env") and path.name != ".env.example":
        violations.append(f"FOUND .env file: {path}")
        continue
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, content):
            violations.append(f"POSSIBLE {label} in {path}")

if violations:
    print("\n".join(violations))
    sys.exit(1)
else:
    print("Secret detection: PASSED")
