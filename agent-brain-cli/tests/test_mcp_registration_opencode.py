"""Tests for MCP server registration into an OpenCode config (`opencode.json`).

OpenCode's MCP schema differs from Claude Code's: servers live under a top-level
``mcp`` key, ``command`` is a single array fusing the executable and its args,
the environment block is ``environment`` (not ``env``), and each entry carries
``type: "local"`` and ``enabled: true``.
"""

import json
from pathlib import Path

from agent_brain_cli.runtime.mcp_registration import (
    build_opencode_mcp_entry,
    register_opencode_mcp,
)


class TestBuildOpenCodeMcpEntry:
    """Unit tests for the OpenCode server-entry builder."""

    def test_default_entry_shape(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".agent-brain"
        entry = build_opencode_mcp_entry(state_dir)
        assert entry["type"] == "local"
        assert entry["enabled"] is True
        # command is a single array (executable + args), not split fields.
        assert entry["command"] == ["agent-brain-mcp", "--backend", "auto"]
        assert "args" not in entry
        assert entry["environment"]["AGENT_BRAIN_STATE_DIR"] == str(state_dir)
        # No-auth default must not inject the client auth toggle.
        assert "AGENT_BRAIN_MCP_AUTH" not in entry["environment"]

    def test_backend_override(self, tmp_path: Path) -> None:
        entry = build_opencode_mcp_entry(tmp_path / ".agent-brain", backend="uds")
        assert entry["command"] == ["agent-brain-mcp", "--backend", "uds"]

    def test_oauth_injects_client_auth_env(self, tmp_path: Path) -> None:
        entry = build_opencode_mcp_entry(tmp_path / ".agent-brain", auth="oauth")
        assert entry["environment"]["AGENT_BRAIN_MCP_AUTH"] == "oauth"

    def test_state_dir_is_absolute(self, tmp_path: Path) -> None:
        entry = build_opencode_mcp_entry(Path(".agent-brain"))
        assert Path(entry["environment"]["AGENT_BRAIN_STATE_DIR"]).is_absolute()


class TestRegisterOpenCodeMcp:
    """Unit tests for merging the entry into an `opencode.json` file."""

    def test_creates_new_config_file(self, tmp_path: Path) -> None:
        config = tmp_path / "opencode.json"
        state_dir = tmp_path / ".agent-brain"
        result = register_opencode_mcp(config, state_dir)
        assert result.action == "created"
        assert config.exists()
        data = json.loads(config.read_text())
        assert data["mcp"]["agent-brain"]["command"][0] == "agent-brain-mcp"
        # A fresh OpenCode config gets the schema marker.
        assert data["$schema"] == "https://opencode.ai/config.json"

    def test_preserves_other_servers_and_keys(self, tmp_path: Path) -> None:
        config = tmp_path / "opencode.json"
        config.write_text(
            json.dumps(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "mcp": {"other": {"type": "local", "command": ["other-mcp"]}},
                    "permission": {"read": {"./x/*": "allow"}},
                }
            )
        )
        result = register_opencode_mcp(config, tmp_path / ".agent-brain")
        assert result.action == "updated"
        data = json.loads(config.read_text())
        # Existing server and unrelated top-level keys are preserved.
        assert data["mcp"]["other"] == {"type": "local", "command": ["other-mcp"]}
        assert data["permission"] == {"read": {"./x/*": "allow"}}
        assert "agent-brain" in data["mcp"]

    def test_idempotent_when_entry_identical(self, tmp_path: Path) -> None:
        config = tmp_path / "opencode.json"
        state_dir = tmp_path / ".agent-brain"
        first = register_opencode_mcp(config, state_dir)
        assert first.action == "created"
        second = register_opencode_mcp(config, state_dir)
        assert second.action == "unchanged"

    def test_updates_when_entry_differs(self, tmp_path: Path) -> None:
        config = tmp_path / "opencode.json"
        state_dir = tmp_path / ".agent-brain"
        register_opencode_mcp(config, state_dir, backend="auto")
        result = register_opencode_mcp(config, state_dir, backend="uds")
        assert result.action == "updated"
        data = json.loads(config.read_text())
        assert data["mcp"]["agent-brain"]["command"] == [
            "agent-brain-mcp",
            "--backend",
            "uds",
        ]

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        config = tmp_path / "opencode.json"
        result = register_opencode_mcp(config, tmp_path / ".agent-brain", dry_run=True)
        assert result.action == "created"
        assert not config.exists()

    def test_corrupt_existing_config_raises_clear_error(self, tmp_path: Path) -> None:
        config = tmp_path / "opencode.json"
        config.write_text("{not valid json")
        try:
            register_opencode_mcp(config, tmp_path / ".agent-brain")
        except ValueError as exc:
            assert "opencode.json" in str(exc)
        else:  # pragma: no cover - explicit failure path
            raise AssertionError("expected ValueError for corrupt config")
