# Plan 03: `file://` handler with sandbox enforcement

**Phase:** 51 — URI schemes + templates
**Requirements covered:** URI-04
**Depends on:** Plan 01 (parameterized dispatcher infrastructure), Phase 50's `agent_brain_server/security/file_sandbox.py` module
**Parallel-safe with:** Plan 02 (`chunk://` + `graph-entity://`) — touches disjoint files (security shim and filesystem-read handler vs. ApiClient HTTP methods)
**Status:** Not started

## Goal

Land the `file://<abs-path>` URI scheme as a direct filesystem read inside the MCP process, gated by the Phase 50 sandbox helper. This is the only scheme that does not hit the FastAPI server — it reads bytes off disk after the path is validated against the dynamically-fetched list of indexed roots from `corpus://folders`. The sandbox helper is re-exported (not forked) from `agent_brain_server.security.file_sandbox` per CONTEXT.md decision E (and the "load-bearing" callout in CONTEXT specifics #2).

Output of this plan: an MCP client calling `resources/read` with `file:///<abs-path>` either receives the file contents (when the path resolves inside an indexed root and passes all sandbox checks), or receives a structured `INVALID_PARAMS` error with the Phase 50-defined `reason` codes (`outside_indexed_roots` | `size_limit` | `hidden_file`).

## Acceptance Criteria

- [ ] `agent_brain_mcp/security/__init__.py` re-exports `is_path_allowed`, `canonicalize_path`, and `MAX_READ_BYTES` from `agent_brain_server.security.file_sandbox` (re-export shim, not fork). Sole source of truth for path policy remains the server module.
- [ ] `.importlinter` adds an explicit allowance for `agent_brain_mcp → agent_brain_server.security` (the existing layering contract forbids `services`, `api`, `indexing`, `storage` but does not name `security`; verify the contract is permissive by default for un-named subpackages, otherwise add a positive allowance).
- [ ] `agent_brain_mcp/resources/parameterized.py` `PARAMETERIZED_HANDLERS["file"]` is implemented as `handle_file_uri`.
- [ ] `parse_uri` extracts the absolute path from `file://<abs-path>` URIs (handles both `file:///abs/path` three-slash and `file://abs/path` two-slash forms; the canonical MCP/RFC 3986 form is three slashes for an absolute path with empty authority).
- [ ] Handler refreshes the allowed roots from `ApiClient.list_folders()` on every read (no cache, per CONTEXT.md decision E).
- [ ] Path canonicalization happens via `canonicalize_path()` before `is_path_allowed` is called (defense against `..` traversal, symlink games).
- [ ] If `is_path_allowed` returns False, raise `McpError(INVALID_PARAMS)` with `data: {"scheme": "file", "path": "<input>", "reason": <Phase 50 reason code>}` — `reason` values are passed through verbatim from Phase 50.
- [ ] Size cap enforced in handler: if file is larger than `MAX_READ_BYTES`, raise `McpError(INVALID_PARAMS)` with `data["reason"] == "size_limit"` (or whatever code Phase 50 chose for over-limit reads) BEFORE attempting to load the file into memory. Use `Path.stat().st_size` for the pre-flight check.
- [ ] Text files (MIME starts with `text/` or in an allowed text-MIME list) return `ReadResourceContents(content=text_body, mime_type=guessed)`.
- [ ] Binary files return `BlobResourceContents` (base64-encoded bytes, MIME `application/octet-stream` or sniffed type). Use the MCP SDK's helper if one exists, otherwise build the type manually.
- [ ] `mimetypes.guess_type(path)` produces the MIME type; fallback `application/octet-stream` for unknown.
- [ ] Filesystem I/O runs through `asyncio.to_thread` to avoid blocking stdio (no `aiofiles` dependency added — keeps dependency surface minimal).
- [ ] All Plan 01 and Plan 02 tests continue to pass (no regression).
- [ ] `task mcp:test`, `task mcp:contract`, `task check:layering`, `task before-push`, `task pr-qa-gate` all exit 0.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/security/__init__.py` | create | Re-export shim. `from agent_brain_server.security.file_sandbox import is_path_allowed, canonicalize_path, MAX_READ_BYTES`. ~10 LOC. |
| `agent-brain-mcp/agent_brain_mcp/resources/parameterized.py` | modify | Extend `parse_uri` for `file://` URIs; implement `handle_file_uri` and wire into `PARAMETERIZED_HANDLERS["file"]`. ~90 LOC delta. |
| `.importlinter` (repo root) | modify (conditional) | If the existing contract blocks `agent_brain_mcp → agent_brain_server.security`, add an exception. Verify first by running `task check:layering` with the import already added. If it passes without change, skip this file. |
| `agent-brain-mcp/tests/test_resources_read_parameterized.py` | modify | Add `file://` test cases. ~140 LOC delta. May split into `test_resources_read_file.py` if the parent file grows past 400 LOC. |
| `agent-brain-mcp/tests/conftest.py` | modify | Add fixture: `tmp_path_with_indexed_root` — creates a tmpdir with subdirs, stubs `ApiClient.list_folders()` to return the tmpdir as the only allowed root. ~30 LOC delta. |

**Estimated total: ~280 LOC (including tests).**

## Implementation Steps

1. **Verify Phase 50 deliverable.** Before writing any code, confirm:
   ```bash
   python -c "from agent_brain_server.security.file_sandbox import is_path_allowed, canonicalize_path, MAX_READ_BYTES; print(is_path_allowed.__doc__)"
   ```
   The import must succeed and the helpers must have the signatures CONTEXT.md decision E assumes. If they differ, file a Phase 50 follow-up issue and BLOCK on it — do not fork the helper. The "share, do not fork" rule is the load-bearing security invariant.

2. **Create `agent_brain_mcp/security/__init__.py`:**
   ```python
   """Re-export sandbox helpers from server package — single source of truth for path policy."""
   from agent_brain_server.security.file_sandbox import (
       MAX_READ_BYTES,
       canonicalize_path,
       is_path_allowed,
   )

   __all__ = ["MAX_READ_BYTES", "canonicalize_path", "is_path_allowed"]
   ```

3. **Verify layering contract.** Run `task check:layering` after the import is in place. If the existing contract (per `docs/plans/2026-05-28-mcp-uds-transport-design.md` §9) blocks the import, add an explicit allowance to `.importlinter`:
   ```toml
   # Carved exception for the sandbox shim — sole purpose is to re-export
   # is_path_allowed/canonicalize_path/MAX_READ_BYTES so MCP and server enforce
   # the same path policy. See docs/plans/2026-06-XX-mcp-v2-subscriptions.md §<phase 51>.
   ```
   Document the carve-out in the contract so future readers understand the reason.

4. **Extend `parse_uri` in `parameterized.py` for `file://`:**
   - Use `urllib.parse.urlsplit` — for `file:///foo/bar`, `parsed.path == "/foo/bar"` and `parsed.netloc == ""`.
   - For `file://foo/bar` (two-slash, treats `foo` as netloc), reject with `data["reason"] = "missing_path"` — clients should always use three slashes for absolute paths.
   - Required: path must be present and start with `/`. Empty path → `data["reason"] = "missing_path"`.
   - Return `ParsedURI(scheme="file", path="/foo/bar")`.

5. **Implement `handle_file_uri` in `parameterized.py`:**
   ```python
   async def handle_file_uri(
       client: ApiClient, params: ParsedURI
   ) -> ReadResourceContents | BlobResourceContents:
       # 1. Refresh allowed roots (no cache — folders can change mid-session)
       folders = await asyncio.to_thread(client.list_folders)
       roots = [f["folder_path"] for f in folders]

       # 2. Canonicalize path (resolves .., symlinks per Phase 50)
       canonical = canonicalize_path(params.path)

       # 3. Sandbox check — Phase 50 returns (allowed: bool, reason: str | None)
       allowed, reason = is_path_allowed(canonical, roots)
       if not allowed:
           raise McpError(ErrorData(
               code=INVALID_PARAMS,
               message=f"file:// access denied: {reason}",
               data={"scheme": "file", "path": params.path, "reason": reason},
           ))

       # 4. Pre-flight size check
       stat = await asyncio.to_thread(canonical.stat)
       if stat.st_size > MAX_READ_BYTES:
           raise McpError(ErrorData(
               code=INVALID_PARAMS,
               message=f"file:// too large: {stat.st_size} > {MAX_READ_BYTES}",
               data={"scheme": "file", "path": params.path, "reason": "size_limit",
                     "size": stat.st_size, "limit": MAX_READ_BYTES},
           ))

       # 5. Read and dispatch to text vs blob
       mime, _ = mimetypes.guess_type(str(canonical))
       mime = mime or "application/octet-stream"
       raw = await asyncio.to_thread(canonical.read_bytes)
       if mime.startswith("text/"):
           try:
               return ReadResourceContents(content=raw.decode("utf-8"), mime_type=mime)
           except UnicodeDecodeError:
               # Mis-typed as text — fall back to blob
               mime = "application/octet-stream"
       return BlobResourceContents(blob=base64.b64encode(raw).decode("ascii"), mimeType=mime)
   ```
   Adjust return types to match the MCP SDK's actual `read_resource` return contract — the existing `read_resource` returns `list[ReadResourceContents | BlobResourceContents]`, so the dispatcher must wrap the handler result in a list. Confirm by re-reading `server.py:147-164` after Plan 01 lands.

6. **Wire `PARAMETERIZED_HANDLERS["file"] = handle_file_uri`** in `parameterized.py`.

7. **Add `tmp_path_with_indexed_root` fixture to `conftest.py`:**
   - Yields `(tmp_path, allowed_root, denied_root)` with a stub `ApiClient.list_folders()` returning only `allowed_root`.
   - Allowed root contains: `allowed.txt` (small text), `allowed.bin` (small binary), `big.txt` (file larger than `MAX_READ_BYTES`).
   - Denied root contains: `secret.txt` (should not be readable).

8. **Add test cases (or new file `tests/test_resources_read_file.py` if the parent file is getting large):**
   - `test_read_file_uri_text_success` — `file:///<tmp>/allowed.txt` returns `ReadResourceContents` with text body.
   - `test_read_file_uri_binary_success` — `file:///<tmp>/allowed.bin` returns `BlobResourceContents` with base64-encoded bytes.
   - `test_read_file_uri_outside_root` — `file:///<denied>/secret.txt` raises `INVALID_PARAMS` with `data["reason"] == "outside_indexed_roots"`.
   - `test_read_file_uri_size_limit` — `file:///<tmp>/big.txt` raises `INVALID_PARAMS` with `data["reason"] == "size_limit"`.
   - `test_read_file_uri_traversal_blocked` — `file:///<tmp>/../etc/passwd` is canonicalized; if it resolves outside the root, raises `outside_indexed_roots`.
   - `test_read_file_uri_symlink_to_outside_blocked` — create a symlink inside allowed root pointing to a denied file; canonicalization should follow the symlink and `is_path_allowed` should reject.
   - `test_read_file_uri_hidden_file_blocked` — if Phase 50 chose to block hidden files (per the `hidden_file` reason code), test that `file:///<tmp>/.secret` raises `INVALID_PARAMS` with `data["reason"] == "hidden_file"`.
   - `test_read_file_uri_missing_path` — `file://` (no path) raises `INVALID_PARAMS` with `data["reason"] == "missing_path"`.
   - `test_read_file_uri_two_slash_form_rejected` — `file://relative/path` (no leading slash) raises `INVALID_PARAMS` with `data["reason"] == "missing_path"`.
   - `test_read_file_uri_roots_refresh_on_each_read` — assert `ApiClient.list_folders()` is called exactly once per `resources/read` call (no caching). Two consecutive reads = two calls.

9. **Run quality gates:**
   ```bash
   cd agent-brain-mcp && poetry run pytest -v
   task mcp:test
   task mcp:contract
   task check:layering
   task before-push
   task pr-qa-gate
   ```

## Verification

- `poetry run pytest agent-brain-mcp/tests/test_resources_read_parameterized.py -v` (or the split file) — all `file://` cases pass; Plan 01/02 regressions stay green.
- `poetry run pytest agent-brain-mcp/tests/ -v` — full MCP test suite passes.
- `task check:layering` — verifies the new `agent_brain_mcp → agent_brain_server.security` import is permitted (either by default or by explicit `.importlinter` carve-out).
- Manual smoke (against a running server with an indexed folder):
  ```bash
  agent-brain start --uds
  agent-brain index ./docs --wait
  # craft a file:// read of a known indexed file
  scripts/mcp-read-file-uri.sh "$(pwd)/docs/USER_GUIDE.md" | agent-brain-mcp --backend uds | \
    jq -e '.result.contents[0].uri | startswith("file://")'
  # try a denied path
  scripts/mcp-read-file-uri.sh "/etc/passwd" | agent-brain-mcp --backend uds | \
    jq -e '.error.data.reason == "outside_indexed_roots"'
  agent-brain stop
  ```
- All five quality gates exit 0.

## Risk Notes

- **Risk (load-bearing):** Forking the sandbox helper into `agent_brain_mcp` would create silent policy drift between server-side `file://` reads (none today) and MCP-side `file://` reads. Mitigation: re-export only. Document explicitly in `agent_brain_mcp/security/__init__.py` docstring that this module MUST NOT contain logic — only re-exports.
- **Risk:** `canonicalize_path` semantics in Phase 50 — if it resolves symlinks (`Path.resolve()`), the `outside_indexed_roots` rejection catches symlink-to-outside attacks for free. If it does NOT resolve symlinks (just `Path.absolute()`), a separate symlink check is needed. Verify with Phase 50 docstring; align test fixtures to match. If unclear, the safe choice is `Path.resolve(strict=False)` semantics.
- **Risk:** `list_folders()` is called on every `file://` read (no cache, per decision E). On a hot path (e.g., MCP client streaming many `file://` reads to render a folder tree), this is one HTTP round-trip per read. This is the documented trade-off — sandbox correctness over latency. If profiling shows it dominates after v2 ships, a short-TTL cache (e.g., 1s) is a future plan, not this plan's job.
- **Risk:** `BlobResourceContents` in the MCP SDK is `(blob: str, mimeType: str | None)` per types.py. The handler must return exactly this shape; mis-spelling field names breaks the JSON-RPC response. Verify by reading the SDK's `BlobResourceContents` definition before writing the test.
- **Risk:** Pre-flight `stat().st_size` is a TOCTOU race — file could grow between stat and read. For the agent-brain threat model (local-first, owner-only sandbox), this is acceptable; document in the handler docstring. A streaming-read with byte counter is the bulletproof solution but adds complexity not warranted in v2.
- **Risk:** `Path.read_bytes()` loads the entire file into memory before base64-encoding. For files up to `MAX_READ_BYTES` (10 MB per Phase 50 default), this is fine. Larger limits would require streaming; Phase 50's 10 MB default is the operative cap.
- **Quality gate:** All five gates exit 0 before push, per CLAUDE.md #1 rule.

---
*Plan 03 of Phase 51*
