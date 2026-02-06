# Code Quality, Linting, and Formatting

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Ruff Configuration](#example-1-ruff-configuration)
  - [Example 2: Pre-commit Hooks](#example-2-pre-commit-hooks)
  - [Example 3: CI/CD Quality Gates](#example-3-cicd-quality-gates)
  - [Example 4: Measuring Code Quality](#example-4-measuring-code-quality)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Command |
|------|---------|
| Install Ruff | `pip install ruff` |
| Check code | `ruff check .` |
| Fix issues | `ruff check --fix .` |
| Format code | `ruff format .` |
| Type check | `mypy src/` |
| Install pre-commit | `pip install pre-commit` |
| Setup hooks | `pre-commit install` |
| Run all hooks | `pre-commit run --all-files` |
| Check complexity | `radon cc src/ --min C` |

---

## Core Concepts

Code quality tools automate enforcement of consistent standards:
- **Linters** (Ruff, Pylint) detect errors and anti-patterns
- **Formatters** (Ruff, Black) enforce consistent style
- **Type checkers** (mypy, pyright) catch type errors statically
- **Complexity analyzers** (radon) identify hard-to-maintain code

The modern Python stack:
- **Ruff**: 10-100x faster than traditional tools, replaces Flake8 + isort + Black
- **mypy**: Industry-standard type checker
- **pre-commit**: Git hooks for automated quality checks

---

## Production Examples

### Example 1: Ruff Configuration

**Use case**: Configure Ruff as an all-in-one linter and formatter.

```toml
# pyproject.toml - Ruff configuration

[tool.ruff]
# Target Python version
target-version = "py312"

# Line length (matches Black)
line-length = 88

# Source directories
src = ["src", "tests"]

# Exclude paths
exclude = [
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    ".eggs",
]

[tool.ruff.lint]
# Enable rule categories
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate (commented code)
    "PL",     # Pylint
    "RUF",    # Ruff-specific rules
]

# Ignore specific rules
ignore = [
    "E501",   # Line too long (handled by formatter)
    "PLR0913", # Too many arguments
]

# Allow autofix for all enabled rules
fixable = ["ALL"]
unfixable = []

# Per-file ignores
[tool.ruff.lint.per-file-ignores]
"tests/*" = [
    "ARG",    # Unused arguments in tests (fixtures)
    "PLR2004", # Magic values in tests
]
"__init__.py" = ["F401"]  # Unused imports in __init__

[tool.ruff.lint.isort]
known-first-party = ["myproject"]
force-single-line = false
lines-after-imports = 2

[tool.ruff.lint.pylint]
max-args = 7
max-branches = 12

[tool.ruff.format]
# Formatting options
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
```

**Running Ruff:**

```bash
#!/bin/bash
# scripts/lint.sh - Linting script

set -e

echo "=== Running Ruff Linter ==="
ruff check .

echo "=== Running Ruff Formatter Check ==="
ruff format --check .

echo "=== All checks passed! ==="
```

**Auto-fix and format:**

```bash
# Fix linting issues and format in one command
ruff check --fix . && ruff format .
```

**Key points**:
- Ruff replaces Flake8, isort, and Black with one fast tool
- Use `select` to enable rule categories by prefix
- `per-file-ignores` handles special cases like tests
- Run in CI to enforce standards

---

### Example 2: Pre-commit Hooks

**Use case**: Automatically run quality checks before every commit.

```yaml
# .pre-commit-config.yaml

# Pre-commit configuration
# Run: pre-commit install (once)
# Run manually: pre-commit run --all-files

repos:
  # Ruff - Linting and formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # mypy - Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.0
          - types-requests
        args: [--strict, --ignore-missing-imports]

  # General pre-commit hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict
      - id: detect-private-key
      - id: no-commit-to-branch
        args: ['--branch', 'main', '--branch', 'master']

  # Security checks
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']
        additional_dependencies: ['bandit[toml]']

  # Commit message format
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.13.0
    hooks:
      - id: commitizen
        stages: [commit-msg]

# CI configuration
ci:
  autofix_commit_msg: |
    [pre-commit.ci] auto fixes from pre-commit hooks
  autofix_prs: true
  autoupdate_branch: ''
  autoupdate_commit_msg: '[pre-commit.ci] pre-commit autoupdate'
  autoupdate_schedule: weekly
  skip: [mypy]  # mypy needs full project context
```

**Installation and usage:**

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks (run once per repo)
pre-commit install
pre-commit install --hook-type commit-msg

# Run all hooks manually
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

**Key points**:
- Hooks run automatically on `git commit`
- `--fix` flag enables auto-correction
- Include security scanning (Bandit)
- Use `no-commit-to-branch` to protect main

---

### Example 3: CI/CD Quality Gates

**Use case**: Enforce quality standards in GitHub Actions.

```yaml
# .github/workflows/quality.yml

name: Code Quality

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint and Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff

      - name: Run Ruff linter
        run: ruff check --output-format=github .

      - name: Run Ruff formatter
        run: ruff format --check .

  type-check:
    name: Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install poetry
          poetry install --with dev

      - name: Run mypy
        run: poetry run mypy src/

  test:
    name: Test with Coverage
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install poetry
          poetry install --with dev

      - name: Run tests with coverage
        run: |
          poetry run pytest --cov=src --cov-report=xml --cov-fail-under=80

      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Bandit
        run: pip install bandit[toml]

      - name: Run Bandit
        run: bandit -c pyproject.toml -r src/
```

**Bandit configuration in pyproject.toml:**

```toml
# pyproject.toml - Security scanning

[tool.bandit]
targets = ["src"]
exclude_dirs = ["tests", ".venv"]
skips = ["B101"]  # Skip assert warnings
```

**Key points**:
- Run linting, type checking, and tests in parallel jobs
- Use `--output-format=github` for inline annotations
- Set `--cov-fail-under=80` to enforce coverage threshold
- Include security scanning as a quality gate

---

### Example 4: Measuring Code Quality

**Use case**: Track complexity and maintainability metrics.

```bash
# Install quality analysis tools
pip install radon xenon

# Calculate cyclomatic complexity
# Shows functions with complexity >= C (Complex)
radon cc src/ --min C --show-complexity

# Calculate maintainability index
# Score: A (high) to F (low maintainability)
radon mi src/ --show

# Fail build if complexity too high
xenon src/ --max-absolute C --max-modules B --max-average B
```

**Python script for quality metrics:**

```python
#!/usr/bin/env python3
"""Quality metrics collection and reporting."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QualityReport:
    """Quality metrics report."""

    complexity_issues: int
    maintainability_avg: float
    test_coverage: float
    lint_errors: int


def run_command(cmd: list[str]) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def check_complexity(src_path: str = "src") -> int:
    """Check cyclomatic complexity, return count of complex functions."""
    code, output = run_command(
        ["radon", "cc", src_path, "--min", "C", "--json"]
    )
    if code != 0 or not output.strip():
        return 0

    import json
    data = json.loads(output)
    return sum(len(funcs) for funcs in data.values())


def check_maintainability(src_path: str = "src") -> float:
    """Get average maintainability index."""
    code, output = run_command(
        ["radon", "mi", src_path, "--json"]
    )
    if code != 0 or not output.strip():
        return 0.0

    import json
    data = json.loads(output)
    scores = [info["mi"] for info in data.values()]
    return sum(scores) / len(scores) if scores else 0.0


def check_lint(src_path: str = ".") -> int:
    """Run Ruff and return error count."""
    code, output = run_command(["ruff", "check", src_path, "--quiet"])
    return output.count("\n") if output else 0


def check_coverage() -> float:
    """Get test coverage percentage."""
    code, output = run_command(
        ["pytest", "--cov=src", "--cov-report=term", "-q"]
    )
    # Parse "TOTAL ... XX%" from output
    for line in output.split("\n"):
        if "TOTAL" in line and "%" in line:
            parts = line.split()
            for part in parts:
                if part.endswith("%"):
                    return float(part[:-1])
    return 0.0


def main() -> int:
    """Generate quality report and check thresholds."""
    print("=== Code Quality Report ===\n")

    report = QualityReport(
        complexity_issues=check_complexity(),
        maintainability_avg=check_maintainability(),
        test_coverage=check_coverage(),
        lint_errors=check_lint(),
    )

    print(f"Complexity Issues (C+): {report.complexity_issues}")
    print(f"Maintainability Index:  {report.maintainability_avg:.1f}")
    print(f"Test Coverage:          {report.test_coverage:.1f}%")
    print(f"Lint Errors:            {report.lint_errors}")

    # Quality gates
    failed = False

    if report.complexity_issues > 5:
        print("\n❌ Too many complex functions")
        failed = True

    if report.maintainability_avg < 65:
        print("\n❌ Maintainability below threshold")
        failed = True

    if report.test_coverage < 80:
        print("\n❌ Test coverage below 80%")
        failed = True

    if report.lint_errors > 0:
        print("\n❌ Lint errors found")
        failed = True

    if not failed:
        print("\n✅ All quality gates passed!")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Key points**:
- Cyclomatic complexity: aim for < 10 per function
- Maintainability index: A (100-20), B (19-10), C (9-0)
- Set quality gates to fail builds on threshold violations

---

## Common Patterns

### Pattern: Makefile Quality Commands
```makefile
.PHONY: lint format check

lint:
	ruff check .
	mypy src/

format:
	ruff format .
	ruff check --fix .

check: lint
	pytest --cov=src --cov-fail-under=80
```

### Pattern: VS Code Settings
```json
{
    "[python]": {
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll": "explicit",
            "source.organizeImports": "explicit"
        },
        "editor.defaultFormatter": "charliermarsh.ruff"
    },
    "ruff.lint.run": "onSave",
    "mypy-type-checker.args": ["--strict"]
}
```

### Pattern: Editor Integration
```bash
# Install VS Code extensions
code --install-extension charliermarsh.ruff
code --install-extension ms-python.mypy-type-checker
code --install-extension ms-python.python
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Suppressing warnings without understanding them
# type: ignore
# noqa
# pylint: disable=all
```

**Do this instead:**
```python
# Be specific about what you're ignoring and why
result = some_function()  # type: ignore[return-value]  # TODO: Fix #123
code = "OK"  # noqa: E501 - URL too long to split
```

---

**Don't do this:**
```yaml
# Disabling pre-commit on merge
SKIP=ruff,mypy git commit -m "Quick fix"
```

**Do this instead:**
```bash
# Fix the issues or use proper escape hatch
git commit -m "WIP: temporary" --no-verify  # Only for true WIP
# Then clean up before merge
```

---

## See Also

- [project-structure.md](project-structure.md) - Project organization
- [ci-cd-pipelines.md](../production/ci-cd-pipelines.md) - Full CI/CD setup
- [pytest-essentials.md](../testing/pytest-essentials.md) - Testing integration
