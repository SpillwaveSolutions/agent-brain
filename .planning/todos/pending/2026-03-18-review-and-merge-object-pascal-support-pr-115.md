---
created: 2026-03-18T02:15:13.510Z
title: Review and merge Object Pascal support PR #115
area: general
files:
  - agent-brain-server/agent_brain_server/indexing/code_chunker.py
  - agent-brain-server/agent_brain_server/config/file_type_presets.py
  - agent-brain-cli/agent_brain_cli/commands/types.py
  - agent-brain-server/tests/unit/test_pascal_chunker.py
---

## Problem

PR #115 (siddsghosh) adds Object Pascal language support (`.pas`, `.pp`, `.lpr`, `.dpr`)
and has been open for 16 days with no reviewer assigned. The PR is well-tested and
self-described as passing `task before-push`. It needs a review and merge before it
gets stale or conflicts accumulate.

PR: https://github.com/SpillwaveSolutions/agent-brain/pull/115

Key changes:
- AST-aware chunking via `tree-sitter-language-pack` bundled `pascal` grammar
- Manual AST walking for `_collect_pascal_symbols` + `_pascal_proc_name`
- Handles qualified names (`procedure TClass.Method`) via `genericDot` grammar node
- Extensions: `.pas`, `.pp`, `.lpr` (Lazarus), `.dpr` (Delphi)
- Content-based fallback detection (unit/program/library headers)
- `"pascal"` preset added to both server (`file_type_presets.py`) and CLI (`types.py`)
- Fixture: `sample.pas` with TShape/TCircle class hierarchy (~115 lines)
- 11 unit tests covering chunker init, symbol extraction, extension detection, presets

## Solution

1. Check out PR branch: `git fetch origin pull/115/head:pr-115 && git checkout pr-115`
2. Run `task before-push` to confirm tests pass locally
3. Review code for correctness (AST walking, symbol extraction edge cases)
4. Verify pascal preset is in sync between server and CLI
5. Merge or request changes via `gh pr review 115`
