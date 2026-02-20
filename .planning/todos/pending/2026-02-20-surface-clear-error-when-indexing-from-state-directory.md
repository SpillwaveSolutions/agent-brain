---
created: 2026-02-20T19:24:12.153Z
title: Surface clear error when indexing from state directory
area: api
severity: low
files:
  - agent-brain-server/agent_brain_server/services/indexing_service.py
  - agent-brain-server/agent_brain_server/indexing/document_loader.py
---

## Problem

`agent-brain index .claude/agent-brain/confluence` returns "No files found" even though the directory contains `.md` files. The `.claude/agent-brain/` path is the state directory, and it appears to be implicitly excluded from indexing.

Root cause is likely one of:
1. The state directory is added to exclude patterns during initialization
2. LlamaIndex's `SimpleDirectoryReader` has issues with hidden directories (`.claude`)

The user gets a confusing "no files found" message with no indication that the path is excluded.

## Solution

If the exclusion is intentional (protecting state data from being indexed), surface a clear error message:

```
Error: Cannot index from state directory '.claude/agent-brain/'.
Move documents outside the state directory and try again.
```

If the exclusion is unintentional (hidden directory issue), fix the `SimpleDirectoryReader` configuration to follow hidden directories when the user explicitly requests them via `--allow-external` or similar flag.

Investigate: check if `.claude` is in the default exclude patterns or if LlamaIndex skips dotfiles/dotdirs by default.
