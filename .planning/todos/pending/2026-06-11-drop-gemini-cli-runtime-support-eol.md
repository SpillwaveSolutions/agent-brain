---
created: 2026-06-11T00:00:00.000Z
title: Drop Gemini CLI runtime support (Gemini CLI is end-of-life)
area: cli
followup_of: Phase 61 discuss-phase (2026-06-11)
files:
  - agent-brain-cli/agent_brain_cli/commands/install_agent.py
  - agent-brain-cli/agent_brain_cli/runtime/gemini_converter.py  # delete
  - agent-brain-cli/agent_brain_cli/runtime/__init__.py
  - agent-brain-cli/agent_brain_cli/runtime/tool_maps.py
  - agent-brain-cli/agent_brain_cli/runtime/types.py
  - agent-brain-cli/agent_brain_cli/config.py
  - agent-brain-cli/agent_brain_cli/config_schema.py
  - agent-brain-cli/agent_brain_cli/diagnostics.py
  - agent-brain-cli/agent_brain_cli/commands/config.py
  - agent-brain-plugin/ (commands/*.md, agents/setup-assistant.md, skills/configuring-agent-brain/**)
---

## Problem

Gemini CLI is end-of-life. Agent Brain still ships first-class `gemini` runtime
support: `install-agent --agent gemini` is a documented, tested path with a
dedicated converter and runtime wiring.

Footprint (from `git grep -li gemini`):
- `commands/install_agent.py` — `gemini` in `RUNTIME_CHOICES` (line 97), the
  attachments map (lines 31-33), and the converter map (line 55); `GeminiConverter`
  import (line 13); help examples (line 167).
- `runtime/gemini_converter.py` — the whole converter (delete candidate).
- `runtime/__init__.py`, `runtime/tool_maps.py`, `runtime/types.py` — gemini enum/
  map entries.
- `config.py`, `config_schema.py`, `diagnostics.py` — gemini references.
- Plugin docs: `agent-brain-config.md`, `agent-brain-install-agent.md`,
  `agent-brain-setup.md`, `agent-brain-providers.md`, `agent-brain-help.md`,
  `agent-brain-embeddings.md`, `agent-brain-summarizer.md`,
  `agents/setup-assistant.md`, `skills/configuring-agent-brain/**`.

## Solution

Remove the `gemini` runtime end-to-end:
1. Drop `gemini` from `RUNTIME_CHOICES`, the attachments map, and the converter
   map in `install_agent.py`; remove the `GeminiConverter` import + help examples.
2. Delete `runtime/gemini_converter.py` and its tests; remove gemini entries from
   `runtime/{__init__,tool_maps,types}.py`, `config.py`, `config_schema.py`,
   `diagnostics.py`.
3. Scrub Gemini from all plugin command/agent/skill docs (CLAUDE.md root table
   already only lists supported runtimes — verify).
4. Decide on a deprecation message: either remove silently (EOL) or have
   `--agent gemini` exit with a clear "Gemini CLI is end-of-life; support removed
   in vX.Y" error for one release. Recommend the loud-error-for-one-release path.

## Acceptance

- `agent-brain install-agent --agent gemini` errors with an EOL message (or the
  choice is gone entirely, per the decision above).
- `git grep -li gemini -- agent-brain-cli/ agent-brain-plugin/` returns only
  intentional historical/CHANGELOG references.
- `task before-push` green; no dead imports.

## Notes

Surfaced during Phase 61 discuss-phase. Also shrinks the parked v9.6.0 Runtime
Parity scope to **Codex + OpenCode only** (Gemini removed from that track too).
Own task — NOT part of Phase 61 (framework matrix).
