"""Client-side OAuth token persistence for Agent Brain MCP (Phase 69 Plan 01).

Implements the SDK ``TokenStorage`` Protocol — four async methods that persist
BOTH the ``OAuthToken`` (the access/refresh token pair) and the
``OAuthClientInformationFull`` (the Dynamic Client Registration result) in a
single JSON file at ``state_dir/mcp-oauth-tokens.json`` with mode ``0o600``.

Persisting the DCR result alongside the token prevents re-registration on
every Pattern A (fresh subprocess) invocation, which would exhaust the
in-memory client registry and degrade performance.

Design reference: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Client-Side Token Storage: FileTokenStorage chmod 0o600 Required (Pattern A)"
  §"Additional Probe: FileTokenStorage chmod 0o600"

Security: ``os.chmod(path, 0o600)`` is called unconditionally after every write
(design-doc Probe 6 + security gate). The test suite asserts the file carries
no group- or world-readable bits.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

logger = logging.getLogger(__name__)

TOKEN_FILE_NAME = "mcp-oauth-tokens.json"
_TOKEN_FILE_MODE = 0o600


class FileTokenStorage:
    """SDK ``TokenStorage`` Protocol implementation that persists one JSON file.

    The file lives at ``state_dir/mcp-oauth-tokens.json`` and carries two
    top-level keys — ``"tokens"`` and ``"client_info"`` — either of which may
    be absent until set.  The file is created with mode ``0o600`` (no group or
    world bits) on every write.

    Args:
        state_dir: Directory where the token file is written.  Created
            automatically on the first write if it does not exist.

    Example::

        storage = FileTokenStorage(state_dir=Path(".agent-brain"))
        await storage.set_tokens(oauth_token)
        token = await storage.get_tokens()   # OAuthToken | None
    """

    def __init__(self, state_dir: Path) -> None:
        """Initialise storage pointing at *state_dir*.

        Args:
            state_dir: Directory under which ``mcp-oauth-tokens.json`` is
                written.  Need not exist yet — it is created on the first write.
        """
        self._state_dir = state_dir
        self._path = state_dir / TOKEN_FILE_NAME

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_raw(self) -> dict[str, Any]:
        """Return the parsed JSON dict from the token file, or ``{}`` on any error.

        Handles three cases without raising:

        * File does not exist → return ``{}``.
        * File exists but cannot be parsed (corrupt, truncated, wrong type) →
          log a WARNING and return ``{}``.
        * Read succeeds → return the dict.

        Returns:
            Parsed JSON dict, or empty dict if the file is absent or corrupt.
        """
        if not self._path.exists():
            return {}
        try:
            return dict(json.loads(self._path.read_text()))
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            logger.warning(
                "corrupt OAuth token file at %s; treating as no-token",
                self._path,
            )
            return {}

    def _write_raw(self, data: dict[str, Any]) -> None:
        """Write *data* as JSON to the token file, then chmod to ``0o600``.

        Mirrors the ``write_mcp_runtime`` idiom from
        ``agent_brain_cli.mcp_runtime`` (issue #179 file-permission convention).

        Args:
            data: Dict to serialise and write.  Must be JSON-serialisable.
        """
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data))
        os.chmod(self._path, _TOKEN_FILE_MODE)

    # ------------------------------------------------------------------
    # TokenStorage Protocol — 4 async methods
    # ------------------------------------------------------------------

    async def get_tokens(self) -> OAuthToken | None:
        """Return the stored ``OAuthToken``, or ``None`` if absent or corrupt.

        Returns:
            Stored ``OAuthToken`` if present and valid, else ``None``.
        """
        raw = self._read_raw()
        tokens_dict = raw.get("tokens")
        if tokens_dict is None:
            return None
        try:
            return OAuthToken.model_validate(tokens_dict)
        except (ValueError, TypeError):
            logger.warning(
                "corrupt OAuth token file at %s; treating as no-token",
                self._path,
            )
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Persist *tokens* to the token file, preserving any existing ``client_info``.

        Args:
            tokens: ``OAuthToken`` to persist.  Serialised via
                ``model_dump(mode="json")`` for cross-platform JSON safety.
        """
        raw = self._read_raw()
        raw["tokens"] = tokens.model_dump(mode="json")
        self._write_raw(raw)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Return the stored ``OAuthClientInformationFull``, or ``None`` if absent.

        Returns:
            Stored ``OAuthClientInformationFull`` if present and valid, else
            ``None``.
        """
        raw = self._read_raw()
        client_dict = raw.get("client_info")
        if client_dict is None:
            return None
        try:
            return OAuthClientInformationFull.model_validate(client_dict)
        except (ValueError, TypeError):
            logger.warning(
                "corrupt OAuth token file at %s; treating as no-token",
                self._path,
            )
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Persist *client_info* to the token file, preserving any existing tokens.

        Storing the DCR registration result alongside the token prevents
        re-registration on every Pattern A (fresh subprocess per CLI call)
        invocation.

        Args:
            client_info: ``OAuthClientInformationFull`` (DCR result) to
                persist.  Serialised via ``model_dump(mode="json")``.
        """
        raw = self._read_raw()
        raw["client_info"] = client_info.model_dump(mode="json")
        self._write_raw(raw)
