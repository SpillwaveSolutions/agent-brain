# Phase 51 — Deferred / Out-of-Scope Items

Items discovered during Phase 51 execution that are NOT in scope for this
phase. Logged here per the GSD scope-boundary rule so they're not lost.

## Pre-existing test failures (discovered during 51-01 execution)

### `tests/test_smoke.py::test_package_imports` (pre-existing, unrelated)

- **Discovered:** Plan 51-01 task 3 (`task before-push` smoke run)
- **Issue:** Hard-coded version assertion
  `agent_brain_mcp.__version__ == "10.0.7"` fails because the package
  shipped 10.1.0 then 10.1.2 since the test was written.
- **Verification it is pre-existing:** `git stash && pytest test_smoke.py`
  on a clean tree (before this plan's changes) reproduces the same
  failure. Not caused by Plan 51-01.
- **Suggested fix (out of scope here):** Either remove the version
  assertion or change it to `>= "10.0.7"`. Probably belongs to a
  trivial chore PR or to Phase 55 (validation/QA gate) when the
  full MCP/UDS suite gets folded into `task before-push`.
- **Impact on Plan 51-01:** zero — the failing assertion is unrelated
  to URI dispatch, the dispatcher tests all pass, and the regression
  suite for `corpus://` reads and the resources/list shape are green.

---

*If Plans 51-02 or 51-03 trip the same failure, they should append to
this file rather than fixing it inline — the fix belongs to a separate
PR/Phase.*
