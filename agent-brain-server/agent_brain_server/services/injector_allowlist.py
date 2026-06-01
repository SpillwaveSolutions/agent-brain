"""Hash-allowlist gate for content-injector scripts (issue #181).

Injector scripts run user-supplied Python in the server process via
``importlib.util.exec_module``. Without a trust gate this is a remote
code execution vector for any caller of ``POST /index`` or
``POST /index/dry-run`` (issue #181, severity: critical).

This module loads a list of allowlisted ``(path, sha256)`` pairs from
the project-local and/or global ``.agent-brain/config.yaml`` and refuses
to permit any script whose resolved path is not listed, or whose file
contents do not hash to the listed sha256. The default — no config or
empty ``injector_scripts:`` — is **fail-closed**: every script is rejected.

Public API:
    is_allowlisted(script_path)  -> bool
    assert_allowlisted(script_path) -> None  # raises PermissionError

Config schema:
    # .agent-brain/config.yaml (project) and/or
    # ~/.config/agent-brain/config.yaml (global)
    # legacy ~/.agent-brain/config.yaml is also accepted
    injector_scripts:
      - path: ./preprocess/enrich.py    # resolved relative to this config file
        sha256: a1b2c3d4e5f6...         # 64-char hex sha256 of the script bytes
      - path: /opt/agent-brain/transforms/normalize.py
        sha256: 7e8f9a0b...

Project entries take precedence over global entries for the same resolved path.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Environment variable for tests / advanced operators to point at a specific
# config file instead of running the standard discovery walk.
_ENV_OVERRIDE = "AGENT_BRAIN_INJECTOR_ALLOWLIST_CONFIG"


@dataclass(frozen=True)
class AllowlistEntry:
    """One allowlisted injector script."""

    resolved_path: Path  # absolute, fully resolved
    sha256: str  # lower-case 64-char hex


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_allowlisted(script_path: Path) -> bool:
    """Return True iff the script is in the allowlist AND hashes match."""
    try:
        assert_allowlisted(script_path)
    except PermissionError:
        return False
    return True


def assert_allowlisted(script_path: Path) -> None:
    """Raise PermissionError if the script is not allowlisted or has been tampered with.

    The error message names the resolved script path and points at the
    config files where it would need to be listed.
    """
    resolved = script_path.expanduser().resolve()

    entries = _load_allowlist()
    entry = entries.get(resolved)
    if entry is None:
        config_locations = ", ".join(str(p) for p in _candidate_config_paths())
        raise PermissionError(
            f"Injector script {resolved} is not in the allowlist. "
            f"Add it to 'injector_scripts:' in one of: {config_locations}. "
            f"See docs/USER_GUIDE.md 'Content Injection' for details."
        )

    actual_hash = _hash_file(resolved)
    if actual_hash != entry.sha256.lower():
        raise PermissionError(
            f"Injector script {resolved} hash does not match the allowlist entry "
            f"(expected {entry.sha256[:12]}…, got {actual_hash[:12]}…). "
            f"The file has changed since it was allowlisted. Re-hash it with "
            f"'sha256sum' and update the allowlist if the change is intended."
        )

    logger.info(
        "Injector script allowlist check passed: %s (sha256=%s…)",
        resolved,
        actual_hash[:12],
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _hash_file(path: Path) -> str:
    """Return the lower-case hex sha256 of the file bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_allowlist() -> dict[Path, AllowlistEntry]:
    """Load and merge project + global allowlists into a path-keyed dict.

    Project entries take precedence over global entries for the same
    resolved path. Returns an empty dict when no config files are found
    or none declare ``injector_scripts``.
    """
    merged: dict[Path, AllowlistEntry] = {}

    # Project layer FIRST so it wins on collisions
    for config_path in _project_config_paths():
        for entry in _entries_from(config_path):
            merged.setdefault(entry.resolved_path, entry)

    # Global layer fills in remaining paths
    for config_path in _global_config_paths():
        for entry in _entries_from(config_path):
            merged.setdefault(entry.resolved_path, entry)

    return merged


def _entries_from(config_path: Path) -> list[AllowlistEntry]:
    """Parse one config file and return its injector_scripts entries.

    Malformed entries are skipped with a warning rather than raising —
    one bad entry shouldn't disable the whole allowlist, but we also
    don't fall back to "allow everything".
    """
    if not config_path.exists():
        return []

    try:
        with config_path.open() as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning(
            "Could not parse injector allowlist config %s: %s", config_path, exc
        )
        return []

    raw_list = data.get("injector_scripts") if isinstance(data, dict) else None
    if not isinstance(raw_list, list):
        return []

    entries: list[AllowlistEntry] = []
    config_dir = config_path.parent
    for idx, raw in enumerate(raw_list):
        entry = _parse_entry(raw, config_dir, config_path, idx)
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_entry(
    raw: Any, config_dir: Path, config_path: Path, idx: int
) -> AllowlistEntry | None:
    """Validate one allowlist entry and resolve its path."""
    if not isinstance(raw, dict):
        logger.warning(
            "Skipping injector_scripts[%d] in %s: not a mapping", idx, config_path
        )
        return None

    path_str = raw.get("path")
    sha = raw.get("sha256")
    if not isinstance(path_str, str) or not isinstance(sha, str):
        logger.warning(
            "Skipping injector_scripts[%d] in %s: needs 'path' and 'sha256' strings",
            idx,
            config_path,
        )
        return None

    sha_clean = sha.strip().lower()
    if len(sha_clean) != 64 or any(c not in "0123456789abcdef" for c in sha_clean):
        logger.warning(
            "Skipping injector_scripts[%d] in %s: sha256 must be 64 hex chars",
            idx,
            config_path,
        )
        return None

    raw_path = Path(path_str).expanduser()
    if not raw_path.is_absolute():
        raw_path = config_dir / raw_path
    resolved = raw_path.resolve()

    return AllowlistEntry(resolved_path=resolved, sha256=sha_clean)


# ---------------------------------------------------------------------------
# Config discovery
# ---------------------------------------------------------------------------


def _candidate_config_paths() -> list[Path]:
    """All config paths the allowlist will inspect, project then global."""
    return list(_project_config_paths()) + list(_global_config_paths())


def _project_config_paths() -> list[Path]:
    """Project-local configs.

    Honors ``AGENT_BRAIN_INJECTOR_ALLOWLIST_CONFIG`` for tests/operators.
    Otherwise walks up from CWD looking for ``.agent-brain/config.yaml``.
    The first match wins (no merging across nested project configs).
    """
    override = os.getenv(_ENV_OVERRIDE)
    if override:
        return [Path(override).expanduser().resolve()]

    paths: list[Path] = []
    current = Path.cwd().resolve()
    root = Path(current.anchor)
    while current != root:
        candidate = current / ".agent-brain" / "config.yaml"
        if candidate.exists():
            paths.append(candidate)
            break
        current = current.parent
    return paths


def _global_config_paths() -> list[Path]:
    """Global configs, XDG location preferred, legacy fallback also checked."""
    paths: list[Path] = []

    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    xdg_dir = (
        Path(xdg_home) / "agent-brain"
        if xdg_home
        else Path.home() / ".config" / "agent-brain"
    )
    xdg_config = xdg_dir / "config.yaml"
    if xdg_config.exists():
        paths.append(xdg_config)

    legacy = Path.home() / ".agent-brain" / "config.yaml"
    if legacy.exists() and legacy not in paths:
        paths.append(legacy)

    return paths
