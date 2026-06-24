"""Tests for MCP server registration into a Claude Code config (`.mcp.json`)."""

import json
from pathlib import Path

from agent_brain_cli.runtime.mcp_registration import (
    build_mcp_server_entry,
    register_claude_mcp,
)


class TestBuildMcpServerEntry:
    """Unit tests for the server-entry builder."""

    def test_default_entry_shape(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".agent-brain"
        entry = build_mcp_server_entry(state_dir)
        assert entry["command"] == "agent-brain-mcp"
        assert entry["args"] == ["--backend", "auto"]
        assert entry["env"]["AGENT_BRAIN_STATE_DIR"] == str(state_dir)
        # No-auth default must not inject the client auth toggle.
        assert "AGENT_BRAIN_MCP_AUTH" not in entry["env"]

    def test_backend_override(self, tmp_path: Path) -> None:
        entry = build_mcp_server_entry(tmp_path / ".agent-brain", backend="uds")
        assert entry["args"] == ["--backend", "uds"]

    def test_oauth_injects_client_auth_env(self, tmp_path: Path) -> None:
        entry = build_mcp_server_entry(tmp_path / ".agent-brain", auth="oauth")
        assert entry["env"]["AGENT_BRAIN_MCP_AUTH"] == "oauth"

    def test_state_dir_is_absolute(self, tmp_path: Path) -> None:
        # A relative state dir should be resolved to absolute (MCP clients run
        # from an unknown cwd, so a relative path would break discovery).
        entry = build_mcp_server_entry(Path(".agent-brain"))
        assert Path(entry["env"]["AGENT_BRAIN_STATE_DIR"]).is_absolute()


class TestRegisterClaudeMcp:
    """Unit tests for merging the entry into a `.mcp.json` file."""

    def test_creates_new_config_file(self, tmp_path: Path) -> None:
        config = tmp_path / ".mcp.json"
        state_dir = tmp_path / ".agent-brain"
        result = register_claude_mcp(config, state_dir)
        assert result.action == "created"
        assert config.exists()
        data = json.loads(config.read_text())
        assert data["mcpServers"]["agent-brain"]["command"] == "agent-brain-mcp"

    def test_preserves_other_servers_and_keys(self, tmp_path: Path) -> None:
        config = tmp_path / ".mcp.json"
        config.write_text(
            json.dumps(
                {
                    "mcpServers": {"other": {"command": "other-mcp"}},
                    "unrelated": {"keep": True},
                }
            )
        )
        result = register_claude_mcp(config, tmp_path / ".agent-brain")
        assert result.action == "updated"
        data = json.loads(config.read_text())
        # Existing server and unrelated top-level keys are preserved.
        assert data["mcpServers"]["other"] == {"command": "other-mcp"}
        assert data["unrelated"] == {"keep": True}
        assert "agent-brain" in data["mcpServers"]

    def test_idempotent_when_entry_identical(self, tmp_path: Path) -> None:
        config = tmp_path / ".mcp.json"
        state_dir = tmp_path / ".agent-brain"
        first = register_claude_mcp(config, state_dir)
        assert first.action == "created"
        second = register_claude_mcp(config, state_dir)
        assert second.action == "unchanged"

    def test_updates_when_entry_differs(self, tmp_path: Path) -> None:
        config = tmp_path / ".mcp.json"
        state_dir = tmp_path / ".agent-brain"
        register_claude_mcp(config, state_dir, backend="auto")
        result = register_claude_mcp(config, state_dir, backend="uds")
        assert result.action == "updated"
        data = json.loads(config.read_text())
        assert data["mcpServers"]["agent-brain"]["args"] == ["--backend", "uds"]

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        config = tmp_path / ".mcp.json"
        result = register_claude_mcp(config, tmp_path / ".agent-brain", dry_run=True)
        assert result.action == "created"
        assert not config.exists()

    def test_corrupt_existing_config_raises_clear_error(self, tmp_path: Path) -> None:
        config = tmp_path / ".mcp.json"
        config.write_text("{not valid json")
        try:
            register_claude_mcp(config, tmp_path / ".agent-brain")
        except ValueError as exc:
            assert ".mcp.json" in str(exc)
        else:  # pragma: no cover - explicit failure path
            raise AssertionError("expected ValueError for corrupt config")
