"""Tests for ``agent-brain start --insecure`` env handling (Issue #199, 199-04).

The CLI's job at start time is to produce the subprocess env dict that the
server's startup gate (199-03) will read. There are three cases:

1. No --insecure, config.json has ``api_key``: env carries ``API_KEY``.
2. No --insecure, env already has API_KEY or AGENT_BRAIN_API_KEY: CLI does
   not overwrite — operator's explicit value wins.
3. ``--insecure``: env carries ``INSECURE_NO_AUTH=true`` and every key var
   is stripped so a stale shell entry can't silently re-enable auth.

We don't need to spawn a real subprocess to test this — the env dict is
constructed in-process and consumed via ``os.execvpe`` / ``subprocess.Popen``,
so the env-construction logic is the testable contract.

Rather than refactor ``start_command`` to factor out env building (a
bigger surface), we monkeypatch ``subprocess.Popen`` and capture the
``env`` kwarg it would have received.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands import start as start_mod


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path: Path) -> Generator[Path, None, None]:
    """A pre-initialized project with config.json carrying an api_key."""
    project = tmp_path / "project"
    project.mkdir()
    state_dir = project / ".agent-brain"
    state_dir.mkdir()
    (state_dir / "data").mkdir()
    (state_dir / "logs").mkdir()
    (state_dir / "config.json").write_text(
        json.dumps(
            {
                "api_key": "file-stored-key",
                "bind_host": "127.0.0.1",
                "port_range_start": 8000,
                "port_range_end": 8100,
                "auto_port": True,
                "project_root": str(project),
            }
        )
    )
    yield project


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip auth env vars + state-dir env so each test starts deterministic."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
    monkeypatch.delenv("INSECURE_NO_AUTH", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_STATE_DIR", raising=False)


@pytest.fixture
def captured_popen(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Capture Popen's env kwarg without actually spawning the server.

    Returns a dict the test asserts on. We also short-circuit the
    health-check loop so start_command's foreground/daemon split doesn't
    hang the test."""
    captured: dict[str, object] = {}

    class _FakeProc:
        pid = 99999

        def poll(self) -> int | None:
            return None

    def _fake_popen(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["env"] = kwargs.get("env")
        captured["cmd"] = args[0] if args else kwargs.get("args")
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    # Pretend the server immediately reports healthy so we don't loop.
    monkeypatch.setattr(start_mod, "check_health", lambda *a, **kw: True)
    return captured


class TestInsecureFlag:
    def test_insecure_sets_no_auth_env_and_strips_keys(
        self,
        runner: CliRunner,
        temp_project: Path,
        captured_popen: dict[str, object],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--insecure → INSECURE_NO_AUTH=true, no key propagation."""
        # A stale shell entry that --insecure must NOT silently honor.
        monkeypatch.setenv("API_KEY", "stale-shell-key")

        result = runner.invoke(
            start_mod.start_command,
            ["--path", str(temp_project), "--insecure"],
        )

        assert result.exit_code == 0, result.output
        env = captured_popen["env"]
        assert isinstance(env, dict)
        assert env.get("INSECURE_NO_AUTH") == "true"
        assert "API_KEY" not in env
        assert "AGENT_BRAIN_API_KEY" not in env

    def test_default_propagates_config_api_key_under_canonical_name(
        self,
        runner: CliRunner,
        temp_project: Path,
        captured_popen: dict[str, object],
    ) -> None:
        """Without --insecure, the file-stored key flows through as API_KEY."""
        result = runner.invoke(start_mod.start_command, ["--path", str(temp_project)])

        assert result.exit_code == 0, result.output
        env = captured_popen["env"]
        assert isinstance(env, dict)
        assert env.get("API_KEY") == "file-stored-key"
        assert "INSECURE_NO_AUTH" not in env

    def test_existing_api_key_env_wins_over_config_file(
        self,
        runner: CliRunner,
        temp_project: Path,
        captured_popen: dict[str, object],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Operator-provided env var beats the file-stored key."""
        monkeypatch.setenv("API_KEY", "shell-provided-key")

        result = runner.invoke(start_mod.start_command, ["--path", str(temp_project)])

        assert result.exit_code == 0, result.output
        env = captured_popen["env"]
        assert isinstance(env, dict)
        assert env.get("API_KEY") == "shell-provided-key"

    def test_legacy_env_var_alone_is_not_overwritten(
        self,
        runner: CliRunner,
        temp_project: Path,
        captured_popen: dict[str, object],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If the operator set AGENT_BRAIN_API_KEY explicitly, we don't shadow
        it with the config-file value under API_KEY — the server's Settings
        validator backfills the legacy env var into API_KEY at startup."""
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "legacy-shell-key")

        result = runner.invoke(start_mod.start_command, ["--path", str(temp_project)])

        assert result.exit_code == 0, result.output
        env = captured_popen["env"]
        assert isinstance(env, dict)
        assert env.get("AGENT_BRAIN_API_KEY") == "legacy-shell-key"
        # Should NOT add API_KEY from config (would override the operator's choice).
        assert "API_KEY" not in env or env.get("API_KEY") is None
