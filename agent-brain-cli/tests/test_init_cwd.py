"""Issue #251: ``agent-brain init`` without ``--path`` uses cwd, not walk-up."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.init import init_command


def test_init_without_path_uses_cwd_not_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A nested folder under an ancestor ``.agent-brain`` gets its own state dir.

    Walk-up is correct for start/query/status, but init means "make this
    directory a project". Adopting ``~/.agent-brain`` (or any ancestor)
    refused with "Configuration already exists" and --force would overwrite
    the global config.
    """
    ancestor = tmp_path / "home"
    ancestor.mkdir()
    (ancestor / ".agent-brain").mkdir()
    (ancestor / ".agent-brain" / "config.json").write_text("{}", encoding="utf-8")

    nested = ancestor / "projects" / "fresh"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    runner = CliRunner()
    with patch("agent_brain_cli.commands.init.migrate_legacy_paths"):
        result = runner.invoke(init_command, ["--no-api-key", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert Path(payload["project_root"]) == nested.resolve()
    local_config = nested / ".agent-brain" / "config.json"
    assert local_config.exists()
    assert Path(payload["config_path"]) == local_config.resolve()
    # Ancestor config is untouched.
    assert (ancestor / ".agent-brain" / "config.json").read_text(
        encoding="utf-8"
    ) == "{}"
