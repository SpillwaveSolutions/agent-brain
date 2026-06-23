"""Unit tests for FileTokenStorage — Phase 69 Plan 01 (OAUTH-07).

Covers:
- Round-trip for OAuthToken (get_tokens / set_tokens)
- Round-trip for OAuthClientInformationFull (get_client_info / set_client_info)
- Coexistence: tokens and client_info live in one file without clobbering each other
- File permission gate: after any write (st_mode & 0o077) == 0 (no group/world bits)
- Cold-start: get_tokens on a non-existent file returns None (no crash)
- Corrupt file: get_tokens / get_client_info log a warning and return None (no raise)
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(**overrides: object) -> OAuthToken:
    """Return a minimal OAuthToken with deterministic field values."""
    defaults: dict[str, object] = {
        "access_token": "tok_test_access",
        "token_type": "Bearer",
        "expires_in": 900,
        "scope": "agent-brain:read agent-brain:index agent-brain:admin",
        "refresh_token": "tok_test_refresh",
    }
    defaults.update(overrides)
    return OAuthToken(**defaults)  # type: ignore[arg-type]


def _make_client_info(**overrides: object) -> OAuthClientInformationFull:
    """Return a minimal OAuthClientInformationFull."""
    defaults: dict[str, object] = {
        "client_id": "test-client-id",
        "redirect_uris": ["http://127.0.0.1:9999/callback"],
        "scope": "agent-brain:read agent-brain:index agent-brain:admin",
        "client_name": "agent-brain-cli",
    }
    defaults.update(overrides)
    return OAuthClientInformationFull(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixture: fresh storage instance in a tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path) -> object:
    """Return a fresh FileTokenStorage pointing at tmp_path."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    return FileTokenStorage(state_dir=tmp_path)


@pytest.fixture()
def storage_path(tmp_path: Path) -> Path:
    """Return the expected token file path."""
    from agent_brain_mcp.oauth.token_storage import TOKEN_FILE_NAME

    return tmp_path / TOKEN_FILE_NAME


# ---------------------------------------------------------------------------
# T1: Round-trip — OAuthToken
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_get_tokens_round_trip(storage: object, storage_path: Path) -> None:
    """set_tokens then get_tokens preserves all fields exactly."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    assert isinstance(storage, FileTokenStorage)
    token = _make_token()

    await storage.set_tokens(token)
    result = await storage.get_tokens()

    assert result is not None
    assert result.access_token == token.access_token
    assert result.token_type == token.token_type
    assert result.expires_in == token.expires_in
    assert result.scope == token.scope
    assert result.refresh_token == token.refresh_token


# ---------------------------------------------------------------------------
# T2: Round-trip — OAuthClientInformationFull
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_get_client_info_round_trip(storage: object) -> None:
    """set_client_info then get_client_info preserves client_id and redirect_uris."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    assert isinstance(storage, FileTokenStorage)
    info = _make_client_info()

    await storage.set_client_info(info)
    result = await storage.get_client_info()

    assert result is not None
    assert result.client_id == info.client_id
    # AnyUrl str comparison
    assert [str(u) for u in result.redirect_uris or []] == [
        str(u) for u in info.redirect_uris or []
    ]


# ---------------------------------------------------------------------------
# T3: Coexistence — tokens and client_info in ONE file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tokens_and_client_info_coexist(
    storage: object, storage_path: Path
) -> None:
    """Setting tokens does not erase client_info and vice versa."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    assert isinstance(storage, FileTokenStorage)
    token = _make_token()
    info = _make_client_info()

    await storage.set_tokens(token)
    await storage.set_client_info(info)

    # Both present in one file
    raw = json.loads(storage_path.read_text())
    assert "tokens" in raw
    assert "client_info" in raw

    # Overwrite tokens only — client_info must survive
    new_token = _make_token(access_token="tok_updated")
    await storage.set_tokens(new_token)
    raw2 = json.loads(storage_path.read_text())
    assert "client_info" in raw2, "set_tokens must not erase client_info"

    # Overwrite client_info only — tokens must survive
    new_info = _make_client_info(client_id="updated-id")
    await storage.set_client_info(new_info)
    raw3 = json.loads(storage_path.read_text())
    assert "tokens" in raw3, "set_client_info must not erase tokens"

    # Read-back still correct
    fetched_token = await storage.get_tokens()
    assert fetched_token is not None
    assert fetched_token.access_token == "tok_updated"

    fetched_info = await storage.get_client_info()
    assert fetched_info is not None
    assert fetched_info.client_id == "updated-id"


# ---------------------------------------------------------------------------
# T4: File permission gate — 0o600 after every write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_file_not_group_world_readable_after_set_tokens(
    storage: object, storage_path: Path
) -> None:
    """After set_tokens the file must have mode 0o600 (no group/world bits)."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    assert isinstance(storage, FileTokenStorage)
    await storage.set_tokens(_make_token())

    assert storage_path.exists(), "Token file must be created"
    file_mode = storage_path.stat().st_mode
    # No group-read, group-write, group-exec, other-read, other-write, other-exec
    assert (file_mode & 0o077) == 0, (
        f"Token file {storage_path} is group/world readable/writable: "
        f"{stat.filemode(file_mode)}"
    )


@pytest.mark.asyncio
async def test_token_file_not_group_world_readable_after_set_client_info(
    storage: object, storage_path: Path
) -> None:
    """After set_client_info the file must have mode 0o600 (no group/world bits)."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    assert isinstance(storage, FileTokenStorage)
    await storage.set_client_info(_make_client_info())

    assert storage_path.exists(), "Token file must be created"
    file_mode = storage_path.stat().st_mode
    assert (file_mode & 0o077) == 0, (
        f"Token file {storage_path} is group/world readable/writable: "
        f"{stat.filemode(file_mode)}"
    )


# ---------------------------------------------------------------------------
# T5: Cold-start — non-existent file → None (no crash)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tokens_returns_none_when_file_absent(storage: object) -> None:
    """get_tokens on a non-existent token file returns None without raising."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    assert isinstance(storage, FileTokenStorage)
    result = await storage.get_tokens()
    assert result is None


@pytest.mark.asyncio
async def test_get_client_info_returns_none_when_file_absent(storage: object) -> None:
    """get_client_info on a non-existent token file returns None without raising."""
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    assert isinstance(storage, FileTokenStorage)
    result = await storage.get_client_info()
    assert result is None


# ---------------------------------------------------------------------------
# T6: Corrupt file — warn + return None (no raise)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tokens_on_corrupt_file_returns_none_and_logs_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """get_tokens on a corrupt JSON file returns None and emits a WARNING log."""
    from agent_brain_mcp.oauth.token_storage import TOKEN_FILE_NAME, FileTokenStorage

    corrupt_path = tmp_path / TOKEN_FILE_NAME
    corrupt_path.write_text("this is not valid json {{{{")

    storage = FileTokenStorage(state_dir=tmp_path)

    import logging

    with caplog.at_level(logging.WARNING, logger="agent_brain_mcp.oauth.token_storage"):
        result = await storage.get_tokens()

    assert result is None
    assert any(
        "corrupt" in record.message.lower() for record in caplog.records
    ), f"Expected a 'corrupt' warning log; got: {[r.message for r in caplog.records]}"


@pytest.mark.asyncio
async def test_get_client_info_on_corrupt_file_returns_none_and_logs_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """get_client_info on a corrupt JSON file returns None and emits a WARNING log."""
    from agent_brain_mcp.oauth.token_storage import TOKEN_FILE_NAME, FileTokenStorage

    corrupt_path = tmp_path / TOKEN_FILE_NAME
    corrupt_path.write_text("{not_json_at_all")

    storage = FileTokenStorage(state_dir=tmp_path)

    import logging

    with caplog.at_level(logging.WARNING, logger="agent_brain_mcp.oauth.token_storage"):
        result = await storage.get_client_info()

    assert result is None
    assert any(
        "corrupt" in record.message.lower() for record in caplog.records
    ), f"Expected a 'corrupt' warning log; got: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# T7: get_tokens returns None when "tokens" key absent (valid JSON, no key)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tokens_returns_none_when_only_client_info_in_file(
    tmp_path: Path,
) -> None:
    """get_tokens returns None if the file exists but has no 'tokens' key."""
    from agent_brain_mcp.oauth.token_storage import TOKEN_FILE_NAME, FileTokenStorage

    token_path = tmp_path / TOKEN_FILE_NAME
    token_path.write_text(
        json.dumps({"client_info": {"client_id": "x", "redirect_uris": []}})
    )

    storage = FileTokenStorage(state_dir=tmp_path)
    result = await storage.get_tokens()
    assert result is None


@pytest.mark.asyncio
async def test_get_client_info_returns_none_when_only_tokens_in_file(
    tmp_path: Path,
) -> None:
    """get_client_info returns None if the file exists but has no 'client_info' key."""
    from agent_brain_mcp.oauth.token_storage import TOKEN_FILE_NAME, FileTokenStorage

    token_path = tmp_path / TOKEN_FILE_NAME
    token_path.write_text(
        json.dumps({"tokens": {"access_token": "t", "token_type": "Bearer"}})
    )

    storage = FileTokenStorage(state_dir=tmp_path)
    result = await storage.get_client_info()
    assert result is None
