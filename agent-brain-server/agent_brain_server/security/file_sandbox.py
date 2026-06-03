"""File sandbox for MCP ``file://`` resource reads.

Source of truth: ``docs/plans/2026-06-02-mcp-v2-subscriptions.md`` §2.5
("Locked ``roots/list`` sandbox policy"). Implements decision A from
``.planning/phases/50-server-endpoint-prep-v2-design-doc/50-CONTEXT.md``.

Key rules
---------
- **Hard whitelist** of canonical absolute paths derived from
  ``folders.list()`` (existing source of truth at
  ``agent_brain_server/api/routers/folders.py``).
- **Canonicalization happens at read time**, not at subscribe/list time.
  Folders may be added or removed during an MCP session; caching the
  decision would silently widen or narrow the sandbox. Callers MUST
  re-invoke :func:`is_path_allowed` on every read.
- **Deny by default** for:

  * ``outside_indexed_roots`` — canonical path (after symlink resolution)
    falls outside every root in ``folders.list()``;
  * ``hidden_file`` — a path component starts with ``.`` AND the path is
    not inside any indexed root (``.env``, ``.ssh/*``, ``~/.config/...``
    when no root covers them);
  * ``symlink_escape`` — the path itself is a symlink whose target
    resolves outside every indexed root;
  * ``size_limit`` — single-file read whose ``st_size`` exceeds
    ``max_bytes`` (default 10 MB; configurable via
    ``Settings.MCP_SANDBOX_MAX_READ_BYTES``).

- **Symlinks are always resolved before policy check.** There is no
  ``--no-resolve`` escape hatch in v2 — that could land in v3 alongside
  authentication.
- **Dot-files INSIDE an indexed root are allowed.** A root may explicitly
  index ``.github/`` or ``.gitignore``; root policy wins. The
  ``hidden_file`` reason fires only when the path is *also* outside every
  indexed root.

Reason precedence (when multiple deny conditions hold)
------------------------------------------------------
When a path falls outside every indexed root, the module reports the
*most specific* reason it can detect:

1. If the literal path is a symlink whose canonical target escapes →
   ``symlink_escape``.
2. Else, if a canonical path component begins with ``.`` →
   ``hidden_file``.
3. Else → ``outside_indexed_roots``.

The size cap is checked only after the path passes the whitelist; an
oversized file outside every root reports the whitelist denial.

TOCTOU and per-file scope
-------------------------
:func:`is_path_allowed` returns a snapshot decision. A symlink could be
swapped between the check and the actual read (TOCTOU). Callers that
need stronger guarantees should ``open`` the file with
``O_NOFOLLOW``-equivalent semantics and re-check ``stat().st_size``
after open. The size cap is a *per-file* policy — concatenated or
streamed multi-file responses must enforce per-response limits
separately at the call site (Phase 51).

Cross-platform note
-------------------
``Path.resolve(strict=False)`` follows symlinks on POSIX and Windows
(Python 3.10+). Agent Brain is local-first POSIX-leaning; Windows
support is best-effort. The module must not crash on Windows but the
hidden-file rule's ``.`` heuristic is POSIX-flavored.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

DEFAULT_MAX_READ_BYTES: int = 10 * 1024 * 1024
"""Default per-file read cap (10 MiB) when callers do not override."""

DenyReason = str
"""Literal reason string returned by :func:`is_path_allowed`.

One of ``"outside_indexed_roots"``, ``"hidden_file"``, ``"symlink_escape"``,
``"size_limit"``.
"""

_DENY_REASONS: frozenset[str] = frozenset(
    {
        "outside_indexed_roots",
        "hidden_file",
        "symlink_escape",
        "size_limit",
    }
)


@runtime_checkable
class _FolderLike(Protocol):
    """Duck-typed protocol for folder records.

    Accepts the existing ``FolderInfo`` / ``FolderRecord`` shapes from
    ``api/routers/folders.py`` without importing them (decouples this
    module from the FastAPI layer).
    """

    folder_path: str


def canonicalize_path(path: str | Path) -> Path:
    """Resolve ``path`` to an absolute canonical form, following symlinks.

    Uses :meth:`pathlib.Path.resolve` with ``strict=False`` so the
    function works even when ``path`` does not exist on disk — useful
    for normalizing inputs before the existence check that
    :func:`is_path_allowed` performs.

    Args:
        path: Filesystem path as a string or :class:`pathlib.Path`.

    Returns:
        Absolute path with symlinks resolved and ``..`` segments
        collapsed.
    """
    return Path(path).resolve(strict=False)


def _is_inside(candidate: Path, root: Path) -> bool:
    """Return True iff ``candidate`` equals ``root`` or is nested under it.

    Both paths must already be canonical. Uses ``Path.parents`` rather
    than string prefix comparison to avoid the ``/foo`` vs ``/foobar``
    false-positive.
    """
    return candidate == root or root in candidate.parents


def _has_dot_component(path: Path) -> bool:
    """Return True iff any component of ``path`` begins with ``.``.

    The root anchor (``/`` or drive letter) is excluded — only proper
    path components count. ``.`` and ``..`` literals are filtered out
    because :func:`canonicalize_path` has already resolved them.
    """
    for part in path.parts:
        if part in ("", "/", "\\"):
            continue
        # Drive letters on Windows look like "C:\\" — skip them too.
        if len(part) >= 2 and part[1] == ":":
            continue
        if part in (".", ".."):
            continue
        if part.startswith("."):
            return True
    return False


def is_path_allowed(
    path: str | Path,
    roots: Sequence[str | Path],
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> tuple[bool, DenyReason | None]:
    """Decide whether ``path`` is readable under the sandbox policy.

    The decision is made at *call time*. Callers MUST NOT cache the
    result across folder mutations — re-invoke per read.

    Args:
        path: The absolute or relative filesystem path to check. The
            function canonicalizes it (resolving symlinks and ``..``
            segments) before applying any rules.
        roots: Iterable of indexed-folder roots. Each entry is
            canonicalized the same way as ``path`` before comparison;
            non-canonical inputs (relative paths, paths with symlinks
            anywhere in the chain) are tolerated.
        max_bytes: Per-file size cap. Defaults to
            :data:`DEFAULT_MAX_READ_BYTES` (10 MiB). Callers may pass
            ``Settings.MCP_SANDBOX_MAX_READ_BYTES``.

    Returns:
        ``(True, None)`` when ``path`` is allowed.

        ``(False, reason)`` otherwise, where ``reason`` is one of:

        - ``"outside_indexed_roots"`` — canonical path is not inside any
          ``roots`` entry, the literal path is not a symlink, and no
          component begins with ``.``;
        - ``"symlink_escape"`` — the literal ``path`` is a symlink and
          its canonical target falls outside every root;
        - ``"hidden_file"`` — canonical path falls outside every root
          AND has a dot-prefixed component;
        - ``"size_limit"`` — canonical path is inside a root, refers to
          an existing regular file, and ``stat().st_size`` exceeds
          ``max_bytes``.

    Notes:
        Phase 51 maps the deny reason into the MCP error envelope:
        ``RESOURCE_NOT_FOUND`` with ``data={"reason": ...}`` so clients
        cannot distinguish "outside sandbox" from "does not exist" — see
        ``docs/plans/2026-06-02-mcp-v2-subscriptions.md`` §2.5.
    """
    canonical = canonicalize_path(path)
    canonical_roots: list[Path] = [canonicalize_path(r) for r in roots]

    inside_root = any(_is_inside(canonical, root) for root in canonical_roots)

    if not inside_root:
        # Rule precedence (most specific wins, see module docstring):
        # symlink_escape → hidden_file → outside_indexed_roots.
        original = Path(path)
        try:
            is_symlink = original.is_symlink()
        except OSError:
            # Broken or unreachable parent; treat as not-a-symlink so we
            # fall through to the hidden / outside checks.
            is_symlink = False

        if is_symlink:
            return False, "symlink_escape"
        if _has_dot_component(canonical):
            return False, "hidden_file"
        return False, "outside_indexed_roots"

    # Path is inside a root. Apply the per-file size cap if the file
    # actually exists as a regular file. Non-existent paths, directories,
    # and special files are NOT size-checked here — Phase 51 enforces
    # type semantics at the read site.
    try:
        if canonical.is_file():
            if canonical.stat().st_size > max_bytes:
                return False, "size_limit"
    except OSError:
        # Stat failure inside a root (permission denied, vanished file)
        # falls through to "allowed" — Phase 51's read site will surface
        # the I/O error to the MCP client.
        pass

    return True, None


def list_sandbox_roots(folders: Iterable[_FolderLike]) -> list[dict[str, str]]:
    """Render the MCP ``roots/list`` response from folder records.

    Accepts duck-typed input so the caller may pass the existing
    ``FolderInfo`` (``api/routers/folders.py``) or ``FolderRecord``
    (folder manager) instances directly — only ``folder_path`` is
    required; ``name`` is derived from the canonical basename when the
    record does not expose one.

    Args:
        folders: Iterable of folder records exposing ``folder_path``
            (and optionally ``name``).

    Returns:
        A list of ``{"uri": "file:///abs/path", "name": "folder-name"}``
        dicts in input order, matching the MCP spec shape for
        ``roots/list``.
    """
    out: list[dict[str, str]] = []
    for record in folders:
        canonical = canonicalize_path(record.folder_path)
        name = getattr(record, "name", None) or canonical.name or str(canonical)
        out.append({"uri": canonical.as_uri(), "name": name})
    return out
