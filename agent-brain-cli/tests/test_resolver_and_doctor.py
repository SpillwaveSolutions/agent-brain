"""Regression tests for the unified resolver (issues #124, #128) and doctor."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.doctor import doctor_command
from agent_brain_cli.config import resolve_project_root
from agent_brain_cli.diagnostics import doctor_hint_message, run_doctor


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test in an isolated cwd with no environment overrides."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENT_BRAIN_URL", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_STATE_DIR", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_CONFIG", raising=False)
    return tmp_path


def test_resolve_project_root_prefers_local_state_dir(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nested ``.agent-brain/`` must win over the git top-level (#124, #128).

    Simulates a mono-repo with the git root one level above a sub-project
    that has its own ``.agent-brain/``. Before the fix the CLI walked to
    the git root and missed the local state dir.
    """
    nested = isolated_cwd / "projects" / "app"
    nested.mkdir(parents=True)
    (nested / ".agent-brain").mkdir()

    # Patch git so it pretends ``isolated_cwd`` (the parent) is the repo top.
    def fake_git(args, *_, **__):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout=str(isolated_cwd) + "\n", stderr=""
        )

    monkeypatch.setattr("subprocess.run", fake_git)

    assert resolve_project_root(nested) == nested


def test_resolve_project_root_falls_back_to_git_root(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no nested .agent-brain/ exists, fall through to the git root."""
    nested = isolated_cwd / "src"
    nested.mkdir()

    def fake_git(args, *_, **__):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout=str(isolated_cwd) + "\n", stderr=""
        )

    monkeypatch.setattr("subprocess.run", fake_git)

    assert resolve_project_root(nested) == isolated_cwd


def test_resolve_project_root_no_git_no_state(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No state dir and no git → fall back to the start path."""

    def fake_git(args, *_, **__):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=args, returncode=128, stdout="", stderr="not a repo"
        )

    monkeypatch.setattr("subprocess.run", fake_git)
    assert resolve_project_root(isolated_cwd) == isolated_cwd


def test_doctor_hint_when_runtime_missing(isolated_cwd: Path) -> None:
    """Hint message must point at the missing runtime.json, not a generic tip."""
    msg = doctor_hint_message(isolated_cwd)
    assert "runtime.json" in msg
    assert "agent-brain init" in msg


def test_doctor_hint_when_runtime_present(isolated_cwd: Path) -> None:
    """When runtime.json exists, the hint is the generic one."""
    state = isolated_cwd / ".agent-brain"
    state.mkdir()
    (state / "runtime.json").write_text("{}")

    msg = doctor_hint_message(isolated_cwd)
    assert "agent-brain doctor" in msg
    assert "runtime.json" not in msg


def test_run_doctor_uninitialized_project(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Doctor returns non-zero and a project_initialized FAIL on a clean dir."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # Pretend cwd is not in a git repo so resolver returns cwd verbatim.
    def fake_git(args, *_, **__):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=args, returncode=128, stdout="", stderr=""
        )

    monkeypatch.setattr("subprocess.run", fake_git)

    report = run_doctor()
    statuses = {c.name: c.status for c in report.checks}
    assert statuses["project_initialized"] == "fail"
    assert report.exit_code == 1


def test_doctor_command_emits_json(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--json output must be parseable and include exit_code."""

    def fake_git(args, *_, **__):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=args, returncode=128, stdout="", stderr=""
        )

    monkeypatch.setattr("subprocess.run", fake_git)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(doctor_command, ["--json"])

    # Doctor exits non-zero on fresh dirs but still emits a JSON body first.
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "checks" in payload
    assert payload["exit_code"] == 1
    assert any(c["name"] == "python_version" for c in payload["checks"])
