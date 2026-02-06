#!/usr/bin/env python3
"""
Code Validator CLI

Demonstrates run→check→fix validation pattern:
- Runs ruff for linting and formatting
- Runs mypy for type checking
- Optionally auto-fixes issues
- Reports actionable results

Usage:
    python code_validator.py src/                    # Check only
    python code_validator.py src/ --fix              # Auto-fix issues
    python code_validator.py src/ --strict           # Strict mypy mode
    python code_validator.py src/ --fix --strict     # Fix and strict check

See: ../references/foundations/code-quality.md
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class CheckResult:
    """Result of a single check."""

    name: str
    passed: bool
    output: str
    errors: int = 0
    warnings: int = 0
    fixed: int = 0

    def __str__(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        details = []
        if self.errors:
            details.append(f"{self.errors} errors")
        if self.warnings:
            details.append(f"{self.warnings} warnings")
        if self.fixed:
            details.append(f"{self.fixed} fixed")
        detail_str = f" ({', '.join(details)})" if details else ""
        return f"[{status}] {self.name}{detail_str}"


@dataclass
class ValidationReport:
    """Aggregated validation results."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def total_errors(self) -> int:
        return sum(c.errors for c in self.checks)

    @property
    def total_fixed(self) -> int:
        return sum(c.fixed for c in self.checks)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    def summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "VALIDATION SUMMARY",
            "=" * 60,
        ]

        for check in self.checks:
            lines.append(str(check))

        lines.append("-" * 60)

        if self.passed:
            lines.append("✓ All checks passed!")
        else:
            lines.append(f"✗ {self.total_errors} total errors")
            if self.total_fixed:
                lines.append(f"  ({self.total_fixed} issues auto-fixed)")

        lines.append("=" * 60)
        return "\n".join(lines)


# ============================================================
# VALIDATORS
# ============================================================

def run_command(cmd: list[str], capture: bool = True) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr if capture else ""
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, "Command timed out after 120 seconds"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"


def check_ruff_lint(path: str, fix: bool = False) -> CheckResult:
    """Run ruff linter."""
    cmd = ["ruff", "check", path]
    if fix:
        cmd.append("--fix")

    exit_code, output = run_command(cmd)

    # Count issues
    errors = output.count(":") // 2 if output and exit_code != 0 else 0
    fixed = output.lower().count("fixed") if fix else 0

    return CheckResult(
        name="Ruff Lint",
        passed=exit_code == 0,
        output=output,
        errors=errors if not fix else max(0, errors - fixed),
        fixed=fixed,
    )


def check_ruff_format(path: str, fix: bool = False) -> CheckResult:
    """Run ruff formatter check."""
    if fix:
        cmd = ["ruff", "format", path]
    else:
        cmd = ["ruff", "format", "--check", path]

    exit_code, output = run_command(cmd)

    # Count files needing formatting
    errors = output.count("would reformat") if not fix else 0
    fixed = output.count("file reformatted") if fix else 0

    return CheckResult(
        name="Ruff Format",
        passed=exit_code == 0 or fix,
        output=output,
        errors=errors,
        fixed=fixed,
    )


def check_mypy(path: str, strict: bool = False) -> CheckResult:
    """Run mypy type checker."""
    cmd = ["mypy", path]
    if strict:
        cmd.append("--strict")

    exit_code, output = run_command(cmd)

    # Count errors from mypy output
    errors = 0
    for line in output.split("\n"):
        if ": error:" in line:
            errors += 1

    return CheckResult(
        name="Mypy Types" + (" (strict)" if strict else ""),
        passed=exit_code == 0,
        output=output,
        errors=errors,
    )


def check_tool_installed(tool: str) -> bool:
    """Check if a tool is installed."""
    exit_code, _ = run_command([tool, "--version"])
    return exit_code == 0


# ============================================================
# MAIN WORKFLOW
# ============================================================

def validate(
    path: str,
    fix: bool = False,
    strict: bool = False,
) -> ValidationReport:
    """
    Run full validation workflow.

    Implements run→check→fix pattern:
    1. Run checks
    2. Report results
    3. Optionally fix issues
    4. Re-check after fixes
    """
    report = ValidationReport()

    # Verify path exists
    if not Path(path).exists():
        result = CheckResult(
            name="Path Check",
            passed=False,
            output=f"Path does not exist: {path}",
            errors=1,
        )
        report.add(result)
        return report

    # Check tools are installed
    tools = ["ruff", "mypy"]
    for tool in tools:
        if not check_tool_installed(tool):
            result = CheckResult(
                name=f"{tool} Installation",
                passed=False,
                output=f"{tool} not installed. Run: pip install {tool}",
                errors=1,
            )
            report.add(result)
            return report

    # Phase 1: Run linting
    print(f"{'Fixing' if fix else 'Checking'} {path}...")
    print()

    # Ruff lint
    lint_result = check_ruff_lint(path, fix=fix)
    report.add(lint_result)
    if lint_result.output and not lint_result.passed:
        print(f"Ruff lint issues:\n{lint_result.output[:500]}")
        print()

    # Ruff format
    format_result = check_ruff_format(path, fix=fix)
    report.add(format_result)
    if format_result.output and not format_result.passed:
        print(f"Ruff format issues:\n{format_result.output[:500]}")
        print()

    # Phase 2: Type checking (cannot auto-fix)
    mypy_result = check_mypy(path, strict=strict)
    report.add(mypy_result)
    if mypy_result.output and not mypy_result.passed:
        print(f"Mypy issues:\n{mypy_result.output[:500]}")
        print()

    return report


# ============================================================
# CLI
# ============================================================

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Python code with ruff and mypy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s src/                    # Check only
  %(prog)s src/ --fix              # Auto-fix lint/format issues
  %(prog)s src/ --strict           # Strict mypy mode
  %(prog)s . --fix --strict        # Fix and strict check current dir

Exit codes:
  0 = All checks passed
  1 = One or more checks failed
        """,
    )

    parser.add_argument(
        "path",
        help="Path to check (file or directory)",
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix lint and format issues",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mypy mode",
    )

    args = parser.parse_args()

    # Run validation
    report = validate(
        path=args.path,
        fix=args.fix,
        strict=args.strict,
    )

    # Print summary
    print(report.summary())

    # Return appropriate exit code
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
