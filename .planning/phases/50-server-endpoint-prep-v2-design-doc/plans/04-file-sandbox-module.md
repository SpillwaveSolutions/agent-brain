# Plan 04: `file_sandbox` security module + `roots/list` policy doc

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirements covered:** URI-04 prerequisite (URI-04 itself lands in Phase 51)
**Depends on:** Plan 01 (v2 design doc must land first — sandbox policy is locked in §2)
**Parallel-safe with:** Plans 02, 03
**Status:** Not started

## Goal

Ship a server-side `file_sandbox` security module that Phase 51's `file://<abs-path>` MCP resource handler will reuse. The module owns canonical path resolution, the `is_path_allowed(path, roots)` decision, and the deny-by-default policy (hidden files outside roots, symlink escape, oversized reads, paths outside indexed roots).

The module is server-internal and does **not** ship a new HTTP endpoint in Phase 50. Phase 51 wires it into the MCP `resources/read` handler. The `roots/list` policy itself (what MCP clients receive when they call `roots/list`) is documented in Plan 01's design doc §2 and reaffirmed here in code-form docstrings, so a future implementer of Phase 51 has zero ambiguity.

## Acceptance Criteria

- [ ] New module `agent-brain-server/agent_brain_server/security/file_sandbox.py` exists with three public functions:
  - `canonicalize_path(path: str | Path) -> Path` — resolves symlinks via `Path.resolve(strict=False)` and returns an absolute canonical path
  - `is_path_allowed(path: str | Path, roots: list[Path], max_bytes: int = 10 * 1024 * 1024) -> tuple[bool, str | None]` — returns `(True, None)` if allowed, else `(False, reason)` where `reason` is one of `"outside_indexed_roots"`, `"hidden_file"`, `"size_limit"`, or `"symlink_escape"`
  - `list_sandbox_roots(folders: Iterable[FolderRecord]) -> list[dict[str, str]]` — returns the MCP `roots/list` response shape: `[{"uri": "file:///abs/path", "name": "folder-name"}, ...]`
- [ ] New `agent-brain-server/agent_brain_server/security/__init__.py` exports the three functions
- [ ] `is_path_allowed` enforces the rules from CONTEXT.md decision A:
  - **Outside indexed roots:** path canonicalizes (after symlink resolution) outside every `roots` entry → deny with reason `"outside_indexed_roots"`
  - **Hidden dot-files outside indexed roots:** any path component starting with `.` AND the path is not inside an indexed root → deny with reason `"hidden_file"` (explicit `.env`, `.git`, `.ssh` patterns, etc.; if inside a root, allowed unless the root itself excludes them — root policy wins)
  - **Symlink escape:** symlink target (after `resolve()`) falls outside every root → deny with reason `"symlink_escape"`
  - **Size cap:** file exists and `stat().st_size > max_bytes` → deny with reason `"size_limit"`
- [ ] No `--no-resolve` escape hatch in v2 (CONTEXT.md decision A — could land in v3 with auth)
- [ ] `canonicalize_path` happens **at read time, not subscribe/list time** — module docstring documents this so the Phase 51 implementer doesn't cache the decision
- [ ] New configuration field `max_file_read_bytes: int = 10_485_760` (10 MB) on `Settings.mcp.sandbox` (or whatever the YAML structure becomes — planner picks; default 10 MB per CONTEXT.md decision A); configurable via YAML and env var; documented in `config/settings.py` docstring
- [ ] Unit tests `tests/security/test_file_sandbox.py` with **positive** and **negative** corpus:
  - **Positive:** read inside an indexed root (canonical, no symlinks) → allowed
  - **Positive:** read inside an indexed root via a symlink whose target is also inside an indexed root → allowed
  - **Positive:** read of a dot-file (e.g., `.gitignore`) **inside** an indexed root → allowed (root policy wins)
  - **Negative:** read of a path outside every indexed root → denied with reason `"outside_indexed_roots"`
  - **Negative:** read of `/etc/passwd` (not in any root) → denied with reason `"outside_indexed_roots"`
  - **Negative:** read of `~/.ssh/id_rsa` (not in any root) → denied with reason `"hidden_file"` or `"outside_indexed_roots"` (whichever predicate hits first; both are correct denies, document the precedence)
  - **Negative:** read of a symlink whose target is `/etc/shadow` (escape) → denied with reason `"symlink_escape"`
  - **Negative:** read of a 20 MB file inside an indexed root → denied with reason `"size_limit"` (use a fixture file or mock `stat()`)
  - **Negative:** read of `..` traversal (e.g., `/indexed/root/../../etc/passwd`) → denied with reason `"outside_indexed_roots"` after canonicalization
- [ ] `list_sandbox_roots` test asserts the response shape exactly matches the MCP spec: `{"uri": "file:///abs/path", "name": "folder-name"}` with `file://` URI scheme
- [ ] Module docstrings explicitly cite Plan 01's design doc §2 sandbox section as the source of truth
- [ ] Module is server-internal — **does not** add any new HTTP routes in this plan (Phase 51 wires it into MCP)
- [ ] `task before-push` passes: Black, Ruff, mypy (strict), pytest with coverage ≥50%
- [ ] No existing server functionality breaks: `task before-push` regression suite continues to pass

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-server/agent_brain_server/security/__init__.py` | create | New package; re-exports the three public functions |
| `agent-brain-server/agent_brain_server/security/file_sandbox.py` | create | The sandbox module itself (~200 LOC including docstrings) |
| `agent-brain-server/agent_brain_server/config/settings.py` | modify | Add `max_file_read_bytes` (or nested `mcp.sandbox.max_read_bytes`) setting with default 10 MB |
| `agent-brain-server/tests/security/__init__.py` | create | Empty file to make `tests/security` a package |
| `agent-brain-server/tests/security/test_file_sandbox.py` | create | Positive + negative corpus unit tests |
| `agent-brain-server/tests/security/test_list_sandbox_roots.py` | create | `list_sandbox_roots` response-shape test |

## Implementation Steps

1. **Re-read Plan 01 design doc §2** for the locked sandbox policy. The design doc wins if it disagrees with CONTEXT.md decision A on any nuance.

2. **Locate the `folders` source of truth.** Confirm where `folders.list()` returns canonical absolute paths — likely `api/routers/folders.py` plus a service layer. The sandbox module accepts roots as a parameter (decoupled from how they're sourced), but Phase 51's caller will pass `folders.list()` results.

3. **Create the `security` package.**
   ```bash
   mkdir -p agent-brain-server/agent_brain_server/security
   touch agent-brain-server/agent_brain_server/security/__init__.py
   ```

4. **Implement `file_sandbox.py`.** Skeleton:
   ```python
   """File sandbox for MCP `file://` resource reads.

   Source of truth: docs/plans/2026-06-02-mcp-v2-subscriptions.md §2 (sandbox policy)
   Implements CONTEXT.md decision A from .planning/phases/50-.../50-CONTEXT.md.

   Key rules:
   - Hard whitelist of canonical absolute paths derived from folders.list()
   - Path canonicalization happens at READ TIME, not subscribe/list time
   - Deny by default for: paths outside indexed roots, hidden dot-files outside
     roots, symlink escapes, single-file reads > max_bytes (default 10 MB)
   - Symlinks resolved before policy check (no escape hatch in v2)
   """
   from __future__ import annotations
   from pathlib import Path
   from typing import Iterable

   DEFAULT_MAX_READ_BYTES = 10 * 1024 * 1024  # 10 MB

   def canonicalize_path(path: str | Path) -> Path:
       """Resolve to an absolute canonical path; symlinks followed."""
       return Path(path).resolve(strict=False)

   def is_path_allowed(
       path: str | Path,
       roots: list[Path],
       max_bytes: int = DEFAULT_MAX_READ_BYTES,
   ) -> tuple[bool, str | None]:
       """Decide whether `path` is allowed under the sandbox policy.

       Returns (True, None) if allowed.
       Returns (False, reason) where reason is one of:
         - "outside_indexed_roots"
         - "hidden_file"
         - "symlink_escape"
         - "size_limit"
       """
       canonical = canonicalize_path(path)
       canonical_roots = [canonicalize_path(r) for r in roots]

       # Rule 1: must canonicalize inside some root
       inside_root = any(
           canonical == root or root in canonical.parents
           for root in canonical_roots
       )
       if not inside_root:
           # Distinguish symlink-escape from plain-outside for better UX
           original = Path(path)
           if original.is_symlink():
               return False, "symlink_escape"
           # Treat dot-files outside roots as hidden_file for clarity
           if any(part.startswith(".") for part in canonical.parts):
               return False, "hidden_file"
           return False, "outside_indexed_roots"

       # Rule 2: size cap (only if file actually exists)
       if canonical.is_file() and canonical.stat().st_size > max_bytes:
           return False, "size_limit"

       return True, None

   def list_sandbox_roots(folders: Iterable) -> list[dict[str, str]]:
       """Return MCP `roots/list` response shape.

       Input: iterable of folder records (must expose .path and .name or
       equivalent — accept duck-typed input so caller can pass the existing
       FolderRecord pydantic model from api/routers/folders.py).
       """
       roots = []
       for f in folders:
           canonical = canonicalize_path(f.path)
           name = getattr(f, "name", None) or canonical.name
           roots.append({"uri": f"file://{canonical}", "name": name})
       return roots
   ```

5. **Add the settings field.** In `config/settings.py`, add `max_file_read_bytes: int = 10 * 1024 * 1024` either flat or under a nested `mcp.sandbox` section (planner picks — note rationale in commit message; CONTEXT.md leaves this to Claude's discretion).

6. **Write positive + negative corpus tests.** In `tests/security/test_file_sandbox.py`, use `tmp_path` fixtures to build a small indexed-roots layout:
   ```
   tmp_path/
   ├── indexed_root_1/
   │   ├── allowed.md
   │   ├── .gitignore        (dot-file inside root — allowed)
   │   └── subdir/
   │       └── nested.txt
   ├── indexed_root_2/
   │   └── data.json
   └── outside/
       ├── secret.txt
       ├── .env              (dot-file outside roots — denied)
       └── big.bin           (20 MB — denied for size)
   ```
   Plus a symlink fixture: `indexed_root_1/escape_link -> outside/secret.txt` to test symlink-escape.
   Test cases (parametrized for clarity):
   ```python
   @pytest.mark.parametrize("relpath, expected", [
       ("indexed_root_1/allowed.md", (True, None)),
       ("indexed_root_1/subdir/nested.txt", (True, None)),
       ("indexed_root_1/.gitignore", (True, None)),
       ("outside/secret.txt", (False, "outside_indexed_roots")),
       ("outside/.env", (False, "hidden_file")),
       # symlink test built separately so we can assert the resolved target
       # size test built separately with a fixture file just over 10 MB or mocked stat()
   ])
   def test_is_path_allowed(tmp_corpus, relpath, expected): ...
   ```
   Build separate tests for the symlink-escape and size-cap cases (they need extra fixture setup or mocking).

7. **Write `list_sandbox_roots` shape test.** In `tests/security/test_list_sandbox_roots.py`, build a list of fake folder records and assert the response is exactly `[{"uri": "file:///abs/path", "name": "folder-name"}, ...]` (canonicalized absolute paths, `file://` scheme).

8. **Wire the settings field through `Settings`.** Confirm it's accessible via `settings.max_file_read_bytes` (or `settings.mcp.sandbox.max_read_bytes`). No call sites need to change in Phase 50 — Phase 51 will consume it.

9. **Run `task before-push` until green.**

## Verification

- **Unit tests:** `cd agent-brain-server && poetry run pytest tests/security/ -v` passes (positive + negative corpus + `list_sandbox_roots` shape).
- **Import-linter:** `task check:layering` continues to exit 0 — the new `security` module sits under `agent_brain_server` so existing contracts don't change, but verify nothing accidentally imports from MCP or CLI.
- **No new HTTP routes:** `git diff` shows zero changes to `api/main.py` and `api/routers/` files. The sandbox module is server-internal; Phase 51 wires it into MCP.
- **Manual smoke** (Python REPL or one-off script):
  ```python
  from agent_brain_server.security import is_path_allowed, canonicalize_path, list_sandbox_roots
  from pathlib import Path
  roots = [Path.cwd() / "agent-brain-server"]
  print(is_path_allowed(Path.cwd() / "agent-brain-server" / "README.md", roots))
  # expect: (True, None)
  print(is_path_allowed("/etc/passwd", roots))
  # expect: (False, 'outside_indexed_roots')
  ```
- **Pre-push gate:** `task before-push` exits 0. Coverage stays ≥50%. Coverage for the new module should be high (>90%) given the small surface — every public function should have at least one test.

## Risk Notes

- **Risk: symlink-escape detection precision.** `Path.is_symlink()` only checks if the path itself is a symlink — if a parent directory is a symlink whose target is outside roots, the canonical resolution catches the escape (the path will canonicalize outside every root and return `"outside_indexed_roots"`). The `"symlink_escape"` reason is informational/UX, not a separate enforcement path. Document this in the module docstring.
- **Risk: TOCTOU between `is_path_allowed` and the actual file read.** A symlink could change between the check and the read. Mitigation: callers should open the file with `O_NOFOLLOW`-equivalent semantics when possible, and re-check `stat().st_size` after open. Note this in the docstring for Phase 51 implementers.
- **Risk: hidden-file rule false-positives.** Some indexed roots may live under `~/.local/share/...` — the entire path has a dot component, but the root itself canonicalizes inside `roots`, so it's allowed. Verify the test corpus covers this: an indexed root under a dot-prefixed parent is allowed; files inside it are allowed.
- **Risk: size-cap edge case for empty files.** A 0-byte file has `st_size == 0` < max_bytes → allowed. Good. Document this.
- **Risk: race between `folders.list()` and read.** Decision A explicitly says canonicalization happens at read time, not subscribe/list time. Phase 51 must call `is_path_allowed` on every read, not cache the decision. Surface this in the module docstring and in Plan 01's design doc.
- **Risk: bypassing the cap via streaming reads.** `is_path_allowed` only checks `st_size` for a single file. If Phase 51 streams a directory listing or concatenates multiple files, the cap is per-file, not per-response. Document the per-file scope; Phase 51 enforces per-response limits separately if needed.
- **Risk: `pathlib.Path.resolve(strict=False)` follows symlinks.** Verified on macOS/Linux Python 3.10+. Confirm behavior matches expectations on Windows if Windows support is in-scope (Agent Brain is local-first POSIX-leaning; Windows support is best-effort, but the module should not crash there).

---
*Plan 04 of Phase 50*
