"""Phase 60 (MCPHYG-01): subprocess hygiene at __init__ — env allowlist,
cwd snapshot/validation, grace_period_s persistence.

Locked CONTEXT decisions:
- DEFAULT_ENV_ALLOWLIST = {PATH, HOME, USER, LANG, LC_ALL, TERM}
- AGENT_BRAIN_API_KEY auto-forwards (v10.2.1 SECURITY-01 carryover)
- OPENAI_API_KEY / ANTHROPIC_API_KEY require explicit forward_env opt-in
- cwd=None snapshots os.getcwd() at construction
- Explicit cwd MUST exist + be a directory (ValueError otherwise)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_brain_mcp.client import DEFAULT_ENV_ALLOWLIST, McpStdioBackend


class TestDefaultEnvAllowlist:
    def test_contains_exactly_six_posix_keys(self) -> None:
        assert DEFAULT_ENV_ALLOWLIST == frozenset(
            {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM"}
        )

    def test_is_frozenset(self) -> None:
        # Mutating must fail — module constant invariant.
        assert isinstance(DEFAULT_ENV_ALLOWLIST, frozenset)


class TestCwdSnapshot:
    def test_cwd_none_snapshots_getcwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        backend = McpStdioBackend("agent-brain-mcp")
        assert backend.cwd == str(tmp_path)

    def test_cwd_explicit_existing_dir_passes(self, tmp_path: Path) -> None:
        backend = McpStdioBackend("agent-brain-mcp", cwd=str(tmp_path))
        assert backend.cwd == str(tmp_path)

    def test_cwd_nonexistent_path_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="cwd"):
            McpStdioBackend("agent-brain-mcp", cwd="/path/that/does/not/exist")

    def test_cwd_file_path_raises_valueerror(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hi")
        with pytest.raises(ValueError, match="cwd"):
            McpStdioBackend("agent-brain-mcp", cwd=str(file_path))


class TestEnvAllowlist:
    def test_openai_api_key_not_auto_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
        backend = McpStdioBackend("agent-brain-mcp")
        env = backend._effective_env()
        assert "OPENAI_API_KEY" not in env

    def test_anthropic_api_key_not_auto_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-leak")
        backend = McpStdioBackend("agent-brain-mcp")
        env = backend._effective_env()
        assert "ANTHROPIC_API_KEY" not in env

    def test_openai_api_key_forwarded_when_explicit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-allowed")
        backend = McpStdioBackend("agent-brain-mcp", forward_env=["OPENAI_API_KEY"])
        env = backend._effective_env()
        assert env.get("OPENAI_API_KEY") == "sk-allowed"

    def test_agent_brain_api_key_auto_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # v10.2.1 SECURITY-01 carryover — server auth key MUST forward.
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "secret-loopback")
        backend = McpStdioBackend("agent-brain-mcp")
        env = backend._effective_env()
        assert env.get("AGENT_BRAIN_API_KEY") == "secret-loopback"

    def test_path_preserved_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH", "/usr/local/bin")
        backend = McpStdioBackend("agent-brain-mcp")
        env = backend._effective_env()
        assert env.get("PATH") == "/usr/local/bin"

    def test_custom_allowlist_replaces_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH", "/usr/local/bin")
        monkeypatch.setenv("HOME", "/Users/test")
        backend = McpStdioBackend("agent-brain-mcp", env_allowlist=frozenset({"PATH"}))
        env = backend._effective_env()
        assert "PATH" in env
        assert "HOME" not in env

    def test_explicit_env_overrides_allowlist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # env= is the escape hatch for tests/advanced ops — caller fully
        # controls the env dict.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
        backend = McpStdioBackend("agent-brain-mcp", env={"FOO": "bar"})
        env = backend._effective_env()
        assert env == {"FOO": "bar"}


class TestGracePeriodPersistence:
    def test_default_grace_is_five_seconds(self) -> None:
        backend = McpStdioBackend("agent-brain-mcp")
        assert backend.grace_period_s == 5.0

    def test_custom_grace_persists(self) -> None:
        backend = McpStdioBackend("agent-brain-mcp", grace_period_s=2.5)
        assert backend.grace_period_s == 2.5

    def test_zero_grace_raises(self) -> None:
        with pytest.raises(ValueError, match="grace_period_s"):
            McpStdioBackend("agent-brain-mcp", grace_period_s=0)

    def test_negative_grace_raises(self) -> None:
        with pytest.raises(ValueError, match="grace_period_s"):
            McpStdioBackend("agent-brain-mcp", grace_period_s=-1.0)


class TestStdioParamsBackwardCompat:
    def test_stdio_params_uses_filtered_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Backward-compat smoke: default kwargs produce a
        # StdioServerParameters whose env was filtered through
        # DEFAULT_ENV_ALLOWLIST.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
        monkeypatch.setenv("PATH", "/usr/local/bin")
        backend = McpStdioBackend("agent-brain-mcp")
        params = backend._stdio_params()
        assert params.env is not None
        assert "OPENAI_API_KEY" not in params.env
        assert params.env.get("PATH") == "/usr/local/bin"

    def test_stdio_params_uses_snapshotted_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        backend = McpStdioBackend("agent-brain-mcp")
        # Caller chdirs after construction — must NOT move the target.
        new_dir = tmp_path / "moved"
        new_dir.mkdir()
        monkeypatch.chdir(new_dir)
        params = backend._stdio_params()
        assert params.cwd == str(tmp_path)
