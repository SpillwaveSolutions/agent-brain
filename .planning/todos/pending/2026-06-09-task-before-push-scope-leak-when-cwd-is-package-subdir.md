---
created: 2026-06-09T05:30:00.000Z
title: task before-push silently scopes to one package when invoked from a subdir, not the full monorepo
area: tooling
files:
  - Taskfile.yml
  - CLAUDE.md
  - .claude/CLAUDE.md
---

## Problem

Running `task before-push` from a package subdirectory (e.g. `agent-brain-mcp/`)
only exercises that package's test suite. CI runs the full monorepo (server +
CLI + mcp + plugin), so a "green local gate" can still ship code that breaks CI.

This bit us on PR #197 (v10.3 phases 56–60). Local `task before-push` reported
`544 passed, 88% coverage — All checks passed` but actually only ran the
agent-brain-mcp package tests. CI then surfaced three CLI failures that were
trivially fixable but cost two extra CI iterations:

1. `test_backend_client_protocol.py::test_backend_client_protocol_declares_expected_methods`
2. `test_mcp_backend_protocol.py::test_mcp_backend_protocol_declares_expected_methods`
3. `test_mcp_start_command.py::test_start_lock_collision_exits_one`

(See merged commit `2d53c76` for the fix.)

CLAUDE.md and `.claude/CLAUDE.md` both say "NEVER PUSH WITHOUT TESTING" and
mandate `task before-push` — but neither warns that the invocation directory
matters, so the rule reads as "I ran the gate, I'm safe."

## Solution

Two options (pick one — or do both):

**Option A — Guard in Taskfile:** Make `before-push` fail fast (or print a loud
banner and re-exec from repo root) when invoked outside the repo root. Catches
the mistake at the moment it happens.

```yaml
before-push:
  preconditions:
    - sh: test "$(pwd)" = "$(git rev-parse --show-toplevel)"
      msg: "task before-push must run from the monorepo root (got $(pwd))"
```

**Option B — Document explicitly:** Update CLAUDE.md and `.claude/CLAUDE.md` to
add a one-line callout under the "NEVER PUSH WITHOUT TESTING" section:

> **Always run `task before-push` from the monorepo root.** Invoking it from a
> package subdirectory silently scopes the gate to that package only — CI will
> still catch the gap, but you'll burn a PR cycle.

Recommended: do A (machine-enforced) since the docs rule already exists and is
easy to forget. B alone won't prevent recurrence.

## Acceptance

- `task before-push` from `agent-brain-mcp/`, `agent-brain-cli/`, or any package
  subdir either re-execs from root or fails with a clear message
- Running from repo root continues to work unchanged
- No false positives when run via CI (CI always runs from repo root)
