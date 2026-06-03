"""Positive + negative corpus for ``is_path_allowed``.

Covers all four documented deny reasons (``outside_indexed_roots``,
``hidden_file``, ``symlink_escape``, ``size_limit``) plus the canonical
allow cases — including dot-files inside an indexed root, nested
subdirectories, symlinks whose target is also inside a root, and the
``..``-traversal escape that resolves outside every root.

Source of truth for the policy is
``docs/plans/2026-06-02-mcp-v2-subscriptions.md`` §2.5.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_brain_server.security.file_sandbox import (
    DEFAULT_MAX_READ_BYTES,
    canonicalize_path,
    is_path_allowed,
)


@pytest.fixture
def corpus(tmp_path: Path) -> dict[str, Path]:
    """Build a small indexed-roots layout under ``tmp_path``.

    Layout::

        tmp_path/
        ├── indexed_root_1/
        │   ├── allowed.md
        │   ├── .gitignore        # dot-file INSIDE root — allowed
        │   └── subdir/
        │       └── nested.txt
        ├── indexed_root_2/
        │   └── data.json
        └── outside/
            ├── secret.txt
            ├── .env              # dot-file OUTSIDE roots — denied
            └── big.bin           # 0-byte placeholder; size-cap test mocks stat()
    """
    root1 = tmp_path / "indexed_root_1"
    root2 = tmp_path / "indexed_root_2"
    outside = tmp_path / "outside"
    for d in (root1, root1 / "subdir", root2, outside):
        d.mkdir(parents=True)

    (root1 / "allowed.md").write_text("hello\n")
    (root1 / ".gitignore").write_text("*.pyc\n")
    (root1 / "subdir" / "nested.txt").write_text("nested\n")
    (root2 / "data.json").write_text("{}\n")
    (outside / "secret.txt").write_text("secret\n")
    (outside / ".env").write_text("API_KEY=...\n")
    (outside / "big.bin").write_text("")  # size mocked in the size-cap test

    return {
        "root1": root1,
        "root2": root2,
        "outside": outside,
        "tmp": tmp_path,
    }


@pytest.fixture
def roots(corpus: dict[str, Path]) -> list[Path]:
    """The two indexed roots used by every test."""
    return [corpus["root1"], corpus["root2"]]


class TestCanonicalizePath:
    """``canonicalize_path`` is a thin wrapper but worth pinning."""

    def test_resolves_relative_to_absolute(self, tmp_path: Path) -> None:
        """A relative input becomes absolute even when it does not exist."""
        result = canonicalize_path("does/not/exist")
        assert result.is_absolute()

    def test_resolves_symlink_target(self, tmp_path: Path) -> None:
        """Following a symlink yields the canonical target path."""
        target = tmp_path / "target.txt"
        target.write_text("ok\n")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        assert canonicalize_path(link) == target.resolve()

    def test_collapses_parent_traversal(self, tmp_path: Path) -> None:
        """``..`` segments collapse — no string-level prefix bypass."""
        weird = tmp_path / "a" / "b" / ".." / ".." / "c"
        canonical = canonicalize_path(weird)
        assert canonical == (tmp_path / "c").resolve()


class TestIsPathAllowedPositive:
    """Paths that should be allowed under the sandbox policy."""

    def test_file_inside_root_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        path = corpus["root1"] / "allowed.md"
        assert is_path_allowed(path, roots) == (True, None)

    def test_nested_file_inside_root_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        path = corpus["root1"] / "subdir" / "nested.txt"
        assert is_path_allowed(path, roots) == (True, None)

    def test_dot_file_inside_root_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """Dot-files inside an indexed root are allowed — root policy wins."""
        path = corpus["root1"] / ".gitignore"
        assert is_path_allowed(path, roots) == (True, None)

    def test_file_in_second_root_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        path = corpus["root2"] / "data.json"
        assert is_path_allowed(path, roots) == (True, None)

    def test_root_itself_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """The root directory itself canonicalizes inside itself."""
        assert is_path_allowed(corpus["root1"], roots) == (True, None)

    def test_symlink_pointing_inside_root_allowed(
        self, corpus: dict[str, Path], roots: list[Path], tmp_path: Path
    ) -> None:
        """Symlink target is itself inside an indexed root → allowed."""
        target = corpus["root1"] / "allowed.md"
        link = corpus["root1"] / "good_link.md"
        link.symlink_to(target)
        assert is_path_allowed(link, roots) == (True, None)

    def test_root_under_dot_prefixed_parent_allowed(self, tmp_path: Path) -> None:
        """A root may live under e.g. ``~/.local/share/...``.

        The dot component sits OUTSIDE the canonical root, so files
        inside the root must still be allowed (regression guard for the
        "Risk: hidden-file rule false-positives" note in the plan).
        """
        weird_root = tmp_path / ".local" / "share" / "agent_brain" / "docs"
        weird_root.mkdir(parents=True)
        target = weird_root / "readme.md"
        target.write_text("ok\n")

        assert is_path_allowed(target, [weird_root]) == (True, None)

    def test_empty_file_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """0-byte file < max_bytes → allowed (boundary case)."""
        path = corpus["root1"] / "empty.txt"
        path.write_text("")
        assert is_path_allowed(path, roots) == (True, None)

    def test_directory_inside_root_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """Directories pass the file-cap check (it's gated on is_file())."""
        path = corpus["root1"] / "subdir"
        assert is_path_allowed(path, roots) == (True, None)

    def test_nonexistent_path_inside_root_allowed(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """Non-existent path inside root is allowed at policy layer.

        Phase 51's read site surfaces the FileNotFoundError as the MCP
        error. The sandbox only enforces *policy*, not existence.
        """
        path = corpus["root1"] / "not_yet.txt"
        assert is_path_allowed(path, roots) == (True, None)


class TestIsPathAllowedNegative:
    """Paths that must be denied — one test per deny reason."""

    def test_path_outside_every_root_denied(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        path = corpus["outside"] / "secret.txt"
        allowed, reason = is_path_allowed(path, roots)
        assert (allowed, reason) == (False, "outside_indexed_roots")

    def test_etc_passwd_denied(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """System file outside every root → denied."""
        allowed, reason = is_path_allowed("/etc/passwd", roots)
        assert allowed is False
        assert reason == "outside_indexed_roots"

    def test_dot_file_outside_root_denied(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """``.env`` outside indexed roots → ``hidden_file``.

        Precedence note: a dot-prefixed path outside every root is
        reported as ``hidden_file`` even though
        ``outside_indexed_roots`` would also be technically correct
        (see module docstring — most-specific reason wins).
        """
        path = corpus["outside"] / ".env"
        allowed, reason = is_path_allowed(path, roots)
        assert (allowed, reason) == (False, "hidden_file")

    def test_ssh_key_path_denied_as_hidden(
        self, tmp_path: Path, roots: list[Path]
    ) -> None:
        """A hypothetical ``~/.ssh/id_rsa`` outside roots → ``hidden_file``."""
        fake_home = tmp_path / "home" / "user"
        ssh_dir = fake_home / ".ssh"
        ssh_dir.mkdir(parents=True)
        key = ssh_dir / "id_rsa"
        key.write_text("PRIVATE\n")

        allowed, reason = is_path_allowed(key, roots)
        assert (allowed, reason) == (False, "hidden_file")

    def test_parent_traversal_escape_denied(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """``/root1/../../outside/secret.txt`` canonicalizes outside."""
        weird = corpus["root1"] / ".." / ".." / "outside" / "secret.txt"
        allowed, reason = is_path_allowed(weird, roots)
        assert allowed is False
        # ``outside`` is not dot-prefixed → reports the plain whitelist denial.
        assert reason == "outside_indexed_roots"

    def test_symlink_escape_denied(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """Symlink inside a root whose target escapes → ``symlink_escape``."""
        target = corpus["outside"] / "secret.txt"
        link = corpus["root1"] / "escape_link"
        link.symlink_to(target)

        allowed, reason = is_path_allowed(link, roots)
        assert (allowed, reason) == (False, "symlink_escape")

    def test_symlink_to_system_file_denied(
        self, corpus: dict[str, Path], roots: list[Path], tmp_path: Path
    ) -> None:
        """Symlink target ``/etc/shadow``-equivalent → ``symlink_escape``.

        Uses an out-of-roots tmp_path file as a stand-in for
        ``/etc/shadow`` because tests must not depend on real system
        files.
        """
        target = tmp_path / "pretend_shadow"
        target.write_text("root:x:0:0\n")
        link = corpus["root1"] / "shadow_link"
        link.symlink_to(target)

        allowed, reason = is_path_allowed(link, roots)
        assert (allowed, reason) == (False, "symlink_escape")

    def test_oversized_file_denied(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """File inside a root whose size exceeds cap → ``size_limit``.

        Mocks ``Path.stat`` so the test stays fast and doesn't write
        20 MB to disk. Behavior matches the production code path —
        the cap is enforced on ``stat().st_size``.
        """
        path = corpus["root1"] / "bigfile.bin"
        path.write_text("placeholder")
        # Resolve once OUTSIDE the patch so the equality check inside
        # ``fake_stat`` never re-enters ``Path.resolve`` (which itself
        # calls ``stat`` — would otherwise infinitely recurse).
        resolved_target = path.resolve()
        real_stat = Path.stat

        def fake_stat(self: Path, *args: object, **kwargs: object) -> object:
            result = real_stat(self, *args, **kwargs)  # type: ignore[arg-type]
            if self == resolved_target:
                # Synthesize an oversized stat result by wrapping the real one.
                class _Bigger:
                    def __init__(self, st: object) -> None:
                        self._st = st

                    def __getattr__(self, name: str) -> object:
                        if name == "st_size":
                            return DEFAULT_MAX_READ_BYTES + 1
                        return getattr(self._st, name)

                return _Bigger(result)
            return result

        with patch.object(Path, "stat", new=fake_stat):
            allowed, reason = is_path_allowed(path, roots)

        assert (allowed, reason) == (False, "size_limit")

    def test_custom_max_bytes_respected(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """Caller-supplied ``max_bytes`` overrides the default."""
        path = corpus["root1"] / "tiny.txt"
        path.write_text("hello, world")  # 12 bytes
        assert is_path_allowed(path, roots, max_bytes=5) == (False, "size_limit")
        assert is_path_allowed(path, roots, max_bytes=100) == (True, None)


class TestIsPathAllowedMisc:
    """Edge cases that don't fit neatly into positive/negative buckets."""

    def test_empty_roots_denies_everything(self, tmp_path: Path) -> None:
        """No indexed roots → nothing is allowed."""
        target = tmp_path / "anywhere.txt"
        target.write_text("nope\n")
        allowed, reason = is_path_allowed(target, [])
        assert allowed is False
        assert reason in _ALL_DENY_REASONS

    def test_string_path_input_accepted(
        self, corpus: dict[str, Path], roots: list[Path]
    ) -> None:
        """The function accepts ``str`` inputs as documented."""
        path = str(corpus["root1"] / "allowed.md")
        assert is_path_allowed(path, roots) == (True, None)

    def test_string_root_input_accepted(self, corpus: dict[str, Path]) -> None:
        """The function accepts ``str`` roots as documented."""
        roots = [str(corpus["root1"]), str(corpus["root2"])]
        path = corpus["root1"] / "allowed.md"
        assert is_path_allowed(path, roots) == (True, None)

    def test_returned_deny_reasons_are_documented(self, tmp_path: Path) -> None:
        """Every reason returned by the module is in the documented set."""
        # Build a few denials and assert the reason vocabulary stays small.
        target = tmp_path / "x.txt"
        target.write_text("x")
        _, reason = is_path_allowed(target, [])
        assert reason in _ALL_DENY_REASONS


_ALL_DENY_REASONS: frozenset[str] = frozenset(
    {
        "outside_indexed_roots",
        "hidden_file",
        "symlink_escape",
        "size_limit",
    }
)
