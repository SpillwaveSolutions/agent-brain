---
description: Switch model profile for GSD agents (quality/balanced/budget/inherit)
argument-hint: <profile (quality|balanced|budget|inherit)>
model: haiku
tools:
  bash: true
---

Show the following output to the user verbatim, with no extra commentary:

!`node "/Users/richardhightower/clients/spillwave/src/agent-brain/.opencode/get-shit-done/bin/gsd-tools.cjs" config-set-model-profile $ARGUMENTS --raw`
