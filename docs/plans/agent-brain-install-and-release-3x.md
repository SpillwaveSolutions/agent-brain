# Plan: Agent Brain Install and Release - Dynamic Version Resolution

**Date:** 2026-02-04
**Goal:** Implement dynamic version resolution for installer and release flows, fix GitHub Actions publish order, and establish planning documentation policy.

---

## Problem Summary

1. **Hardcoded 2.0.0 in release skill** - `.claude/skills/agent-brain-release/SKILL.md` says "Latest Release: v2.0.0" and all install examples pin to 2.0.0
2. **Plugin skill metadata outdated** - Both plugin skills have `version: 2.0.0` in metadata:
   - `agent-brain-plugin/skills/using-agent-brain/SKILL.md` line 19
   - `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` line 16
3. **No version selection in installer** - `agent-brain-plugin/commands/agent-brain-install.md` installs unpinned packages without asking user for version
4. **GitHub Actions race condition** - `publish-to-pypi.yml` runs server and CLI publish in parallel; no wait for PyPI propagation

**Note:** CLI pyproject.toml already has `agent-brain-rag = "^3.0.0"` (PyPI dependency, not path) - no sed rewrite needed in workflow.

---

## Files to Modify

| File | Change |
|------|--------|
| `.claude/skills/agent-brain-release/SKILL.md` | Add version resolver, remove hardcoded 2.0.0 |
| `agent-brain-plugin/skills/using-agent-brain/SKILL.md` | Update metadata version 2.0.0 → 3.0.0 |
| `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` | Update metadata version 2.0.0 → 3.0.0, update example output |
| `agent-brain-plugin/commands/agent-brain-install.md` | Add version selection with resolver |
| `.github/workflows/publish-to-pypi.yml` | Sequential publish with PyPI wait |
| `.github/workflows/pr-qa-gate.yml` | Add version alignment CI check (optional) |

---

## Core Concept: Version Resolver

Both the release skill and install command will use the same resolver pattern:

```bash
# Get latest version from PyPI
LATEST=$(curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])")

# Fallback to pyproject.toml if PyPI unreachable
if [ -z "$LATEST" ]; then
  LATEST=$(grep '^version = ' agent-brain-server/pyproject.toml | cut -d'"' -f2)
fi
```

This ensures examples always show `==<resolved_version>` rather than a hardcoded number.

---

## Implementation Steps

### Step 1: Meta/Process - Planning Policy (DONE)

CLAUDE.md and AGENTS.md already have the planning rule on line 5.

---

### Step 2: Update Release Skill with Resolver

**File:** `.claude/skills/agent-brain-release/SKILL.md`

Replace "Current Version" section with version resolution pattern and update all install examples to use resolver.

---

### Step 3: Update Plugin Skill Metadata

**File:** `agent-brain-plugin/skills/using-agent-brain/SKILL.md`
- Line 19: `version: 2.0.0` → `version: 3.0.0`

**File:** `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md`
- Line 16: `version: 2.0.0` → `version: 3.0.0`
- Line 114: Update example output to show dynamic pattern
- Line 155: "Agent Brain 2.0 supports" → "Agent Brain supports"

---

### Step 4: Add Version Selection to Install Command

**File:** `agent-brain-plugin/commands/agent-brain-install.md`

Add Step 1.5 with version resolver and user question. Update all installation commands to use resolved version variable.

---

### Step 5: Fix GitHub Actions Publish Order

**File:** `.github/workflows/publish-to-pypi.yml`

- Change `publish-cli` to depend on `publish-server`
- Add PyPI wait step with 30 retry loop (10s each)

---

### Step 6: Add Version Alignment CI Check (Optional)

**File:** `.github/workflows/pr-qa-gate.yml`

Add step to verify server and CLI versions match.

---

## Verification Steps

After implementation:

1. **Check hardcoded version references removed:**
   ```bash
   grep -rn "==2\.0\.0\|v2\.0\.0" .claude/skills/ agent-brain-plugin/
   # Should return no matches (or only in changelog/history sections)
   ```

2. **Verify resolver works:**
   ```bash
   curl -sf https://pypi.org/pypi/agent-brain-rag/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
   ```

3. **Test install command flow manually**

---

## Acceptance Criteria

- [x] Plan saved to `docs/plans/agent-brain-install-and-release-3x.md`
- [x] Release skill uses resolver pattern, no hardcoded version numbers in examples
- [x] Plugin skill metadata updated to 3.0.0
- [x] Install command resolves version dynamically, asks user, pins installs
- [x] GitHub Action: publish-cli depends on publish-server + PyPI wait loop
- [x] CI check validates server/CLI version alignment
