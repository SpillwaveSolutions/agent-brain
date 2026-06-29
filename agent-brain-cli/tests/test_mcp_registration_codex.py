"""Tests for MCP server registration into a Codex config (`config.toml`).

Codex stores MCP servers as TOML tables under ``[mcp_servers.<name>]`` in
``$CODEX_HOME/config.toml`` (default ``~/.codex/config.toml``). The entry shape
mirrors Claude Code's (``command`` string, ``args`` array, ``env`` table) but the
file is TOML, so the writer merges with tomlkit and preserves the rest of the
user's config (other servers, top-level keys, comments).
"""

from pathlib import Path

import tomlkit

from agent_brain_cli.runtime.mcp_registration import register_codex_mcp


class TestRegisterCodexMcp:
    def test_creates_new_config_file(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        state_dir = tmp_path / ".agent-brain"
        result = register_codex_mcp(config, state_dir)
        assert result.action == "created"
        assert config.exists()
        doc = tomlkit.parse(config.read_text())
        entry = doc["mcp_servers"]["agent-brain"]
        assert entry["command"] == "agent-brain-mcp"
        assert list(entry["args"]) == ["--backend", "auto"]
        assert entry["env"]["AGENT_BRAIN_STATE_DIR"] == str(state_dir)
        assert "AGENT_BRAIN_MCP_AUTH" not in entry["env"]

    def test_backend_override(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        register_codex_mcp(config, tmp_path / ".agent-brain", backend="uds")
        doc = tomlkit.parse(config.read_text())
        assert list(doc["mcp_servers"]["agent-brain"]["args"]) == [
            "--backend",
            "uds",
        ]

    def test_oauth_injects_client_auth_env(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        register_codex_mcp(config, tmp_path / ".agent-brain", auth="oauth")
        doc = tomlkit.parse(config.read_text())
        env = doc["mcp_servers"]["agent-brain"]["env"]
        assert env["AGENT_BRAIN_MCP_AUTH"] == "oauth"

    def test_state_dir_is_absolute(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        register_codex_mcp(config, Path(".agent-brain"))
        doc = tomlkit.parse(config.read_text())
        state = doc["mcp_servers"]["agent-brain"]["env"]["AGENT_BRAIN_STATE_DIR"]
        assert Path(state).is_absolute()

    def test_preserves_other_servers_keys_and_comments(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text(
            "# my codex config\n"
            'approval_policy = "on-request"\n'
            "\n"
            "[mcp_servers.docs]\n"
            'command = "docs-server"\n'
            'args = ["--stdio"]\n'
        )
        result = register_codex_mcp(config, tmp_path / ".agent-brain")
        assert result.action == "updated"
        text = config.read_text()
        doc = tomlkit.parse(text)
        # Other server, top-level key, and the comment all survive.
        assert doc["mcp_servers"]["docs"]["command"] == "docs-server"
        assert doc["approval_policy"] == "on-request"
        assert "# my codex config" in text
        assert "agent-brain" in doc["mcp_servers"]

    def test_idempotent_when_entry_identical(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        state_dir = tmp_path / ".agent-brain"
        first = register_codex_mcp(config, state_dir)
        assert first.action == "created"
        second = register_codex_mcp(config, state_dir)
        assert second.action == "unchanged"

    def test_updates_when_entry_differs(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        state_dir = tmp_path / ".agent-brain"
        register_codex_mcp(config, state_dir, backend="auto")
        result = register_codex_mcp(config, state_dir, backend="uds")
        assert result.action == "updated"
        doc = tomlkit.parse(config.read_text())
        assert list(doc["mcp_servers"]["agent-brain"]["args"]) == [
            "--backend",
            "uds",
        ]

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        result = register_codex_mcp(config, tmp_path / ".agent-brain", dry_run=True)
        assert result.action == "created"
        assert not config.exists()

    def test_corrupt_existing_config_raises_clear_error(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text("this is = = not valid toml [[[")
        try:
            register_codex_mcp(config, tmp_path / ".agent-brain")
        except ValueError as exc:
            assert "config.toml" in str(exc)
        else:  # pragma: no cover - explicit failure path
            raise AssertionError("expected ValueError for corrupt config")
