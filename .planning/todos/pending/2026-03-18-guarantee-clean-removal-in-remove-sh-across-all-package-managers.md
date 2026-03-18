---
created: 2026-03-18T17:07:17.591Z
title: Guarantee clean removal in remove.sh across all package managers
area: tooling
files:
  - .claude/skills/installing-local/remove.sh
---

## Problem

`/ag-remove-local-install` currently warns if `agent-brain` is still found in PATH after removal but does not clean it up. The binary can survive removal if installed via a package manager not yet targeted (homebrew, a pip --user install, a pyenv shim, etc.). Additionally, the zero-state cleanup references `~/.claude/agent-brain` which has been superseded by `~/.config/agent-brain` as the canonical state directory.

## Solution

1. **Update state dir reference**: replace `~/.claude/agent-brain` in the zero-state step with `~/.config/agent-brain`.

2. **Add guaranteed-clean verification loop** at the end of remove.sh:
   - After all removal steps, loop on `which agent-brain`
   - Detect install source from the resolved path:
     - `~/.local/share/uv/` or `~/.local/bin/` → `uv tool uninstall agent-brain-cli`
     - `~/.local/share/pipx/` or pipx bin → `pipx uninstall agent-brain-cli`
     - `/opt/homebrew/` or `/usr/local/Cellar/` → `brew uninstall agent-brain`
     - `~/.pyenv/shims/` → `pyenv rehash` then delete shim directly
     - any venv/site-packages path → `pip uninstall -y agent-brain-cli agent-brain-rag`
   - Repeat until `which agent-brain` returns nothing OR no more known strategies remain
   - If still found after exhausting strategies, print clear error with the path so the user knows what to manually remove

3. Handle both `agent-brain` and `agent-brain-serve` binaries in the loop.
