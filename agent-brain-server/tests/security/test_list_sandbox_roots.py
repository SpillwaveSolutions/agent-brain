"""Response-shape tests for ``list_sandbox_roots``.

The function renders the MCP ``roots/list`` payload from an iterable of
folder records. The shape must match the MCP spec verbatim:
``[{"uri": "file:///abs/path", "name": "folder-name"}, ...]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_brain_server.security.file_sandbox import list_sandbox_roots


@dataclass
class _FakeFolder:
    """Minimal duck-typed folder record used by the tests."""

    folder_path: str
    name: str | None = None


def test_returns_mcp_spec_shape(tmp_path: Path) -> None:
    """Each entry has exactly two keys: ``uri`` and ``name``."""
    root = tmp_path / "docs"
    root.mkdir()
    result = list_sandbox_roots([_FakeFolder(folder_path=str(root), name="docs")])

    assert result == [{"uri": root.as_uri(), "name": "docs"}]
    assert set(result[0].keys()) == {"uri", "name"}


def test_uri_uses_file_scheme(tmp_path: Path) -> None:
    """All URIs use the ``file://`` scheme with absolute paths."""
    root = tmp_path / "code"
    root.mkdir()
    result = list_sandbox_roots([_FakeFolder(folder_path=str(root), name="code")])

    assert result[0]["uri"].startswith("file://")
    # Path between file:// and end is absolute and canonical.
    assert result[0]["uri"] == root.resolve().as_uri()


def test_preserves_input_order(tmp_path: Path) -> None:
    """Output order matches input order; no sorting applied."""
    a = tmp_path / "z_first"
    b = tmp_path / "a_second"
    c = tmp_path / "m_third"
    for d in (a, b, c):
        d.mkdir()

    result = list_sandbox_roots(
        [
            _FakeFolder(folder_path=str(a), name="z"),
            _FakeFolder(folder_path=str(b), name="a"),
            _FakeFolder(folder_path=str(c), name="m"),
        ]
    )

    assert [entry["name"] for entry in result] == ["z", "a", "m"]


def test_name_derived_from_basename_when_missing(tmp_path: Path) -> None:
    """Records without a ``name`` attr default to the canonical basename."""
    root = tmp_path / "auto_named"
    root.mkdir()
    # Use a tuple-style fake record that exposes only ``folder_path``.

    class _NameLess:
        def __init__(self, p: str) -> None:
            self.folder_path = p

    result = list_sandbox_roots([_NameLess(str(root))])
    assert result == [{"uri": root.as_uri(), "name": "auto_named"}]


def test_paths_canonicalized(tmp_path: Path) -> None:
    """Symlinked and relative inputs canonicalize before rendering."""
    target = tmp_path / "real_root"
    target.mkdir()
    link = tmp_path / "link_root"
    link.symlink_to(target)

    result = list_sandbox_roots([_FakeFolder(folder_path=str(link), name="link")])
    # URI should point to the symlink target, not the link itself.
    assert result[0]["uri"] == target.resolve().as_uri()


def test_empty_input_returns_empty_list() -> None:
    """No folders → empty list (not None)."""
    assert list_sandbox_roots([]) == []


def test_accepts_generator_input(tmp_path: Path) -> None:
    """``Iterable[_FolderLike]`` accepts a generator, not just a list."""
    root = tmp_path / "gen_root"
    root.mkdir()

    def _gen() -> object:
        yield _FakeFolder(folder_path=str(root), name="gen")

    result = list_sandbox_roots(_gen())  # type: ignore[arg-type]
    assert result == [{"uri": root.as_uri(), "name": "gen"}]
