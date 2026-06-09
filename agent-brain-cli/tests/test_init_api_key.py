"""Tests for ``agent-brain init`` API key generation (Issue #179).

Covers:

- Default flow: ``init`` writes ``api_key`` to ``config.json``.
- ``--no-api-key`` opt-out: no ``api_key`` field in ``config.json``.
- Generated key has the expected entropy (urlsafe, 32-byte source).
- ``config.json`` is chmod'd to ``0o600`` since it carries a secret.
- ``resolve_api_key`` falls back to ``config.json`` when no env var or
  runtime.json is present (the post-init / pre-start window).
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.init import init_command
from agent_brain_cli.config import resolve_api_key


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a fresh project root for init to populate."""
    project = tmp_path / "project"
    project.mkdir()
    yield project


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Strip Agent Brain env vars *and* the canonical ``API_KEY`` so the test
    exercises the file-fallback path even when the dev shell has API_KEY set."""
    candidates = {
        k for k in os.environ if k.startswith("AGENT_BRAIN_") or k == "API_KEY"
    }
    saved = {k: os.environ.pop(k) for k in candidates}
    try:
        yield
    finally:
        for k in candidates:
            os.environ.pop(k, None)
        os.environ.update(saved)


class TestInitGeneratesApiKey:
    def test_default_init_writes_api_key_to_config(
        self, runner: CliRunner, temp_project: Path
    ) -> None:
        result = runner.invoke(init_command, ["--path", str(temp_project)])

        assert result.exit_code == 0, result.output

        config_path = temp_project / ".agent-brain" / "config.json"
        config = json.loads(config_path.read_text())

        assert "api_key" in config
        assert isinstance(config["api_key"], str)
        # secrets.token_urlsafe(32) produces ~43 char base64-urlsafe string.
        assert len(config["api_key"]) >= 32

    def test_no_api_key_flag_omits_field(
        self, runner: CliRunner, temp_project: Path
    ) -> None:
        result = runner.invoke(
            init_command, ["--path", str(temp_project), "--no-api-key"]
        )

        assert result.exit_code == 0, result.output

        config_path = temp_project / ".agent-brain" / "config.json"
        config = json.loads(config_path.read_text())

        assert "api_key" not in config

    def test_config_json_chmod_0600(
        self, runner: CliRunner, temp_project: Path
    ) -> None:
        result = runner.invoke(init_command, ["--path", str(temp_project)])
        assert result.exit_code == 0, result.output

        config_path = temp_project / ".agent-brain" / "config.json"
        mode = stat.S_IMODE(config_path.stat().st_mode)
        assert mode == 0o600, f"config.json mode is {oct(mode)}, expected 0o600"

    def test_two_init_runs_produce_different_keys(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """No key reuse across projects — each init should be independent."""
        project_a = tmp_path / "project-a"
        project_b = tmp_path / "project-b"
        project_a.mkdir()
        project_b.mkdir()

        runner.invoke(init_command, ["--path", str(project_a)])
        runner.invoke(init_command, ["--path", str(project_b)])

        key_a = json.loads((project_a / ".agent-brain" / "config.json").read_text())[
            "api_key"
        ]
        key_b = json.loads((project_b / ".agent-brain" / "config.json").read_text())[
            "api_key"
        ]

        assert key_a != key_b


class TestResolveApiKeyConfigFallback:
    def test_falls_back_to_config_json_when_no_env_or_runtime(
        self,
        clean_env: None,
        tmp_path: Path,
    ) -> None:
        """Post-init / pre-start window: config.json has it, runtime.json doesn't."""
        (tmp_path / "config.json").write_text(
            json.dumps({"api_key": "config-stored-key", "bind_host": "127.0.0.1"})
        )

        assert resolve_api_key(tmp_path) == "config-stored-key"

    def test_runtime_json_still_takes_precedence_over_config_json(
        self,
        clean_env: None,
        tmp_path: Path,
    ) -> None:
        """When server writes runtime.json, that wins over config.json."""
        (tmp_path / "config.json").write_text(json.dumps({"api_key": "config-key"}))
        (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "runtime-key"}))

        assert resolve_api_key(tmp_path) == "runtime-key"
