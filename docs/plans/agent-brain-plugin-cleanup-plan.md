# Plan: Agent Brain Plugin Cleanup & Skill Improvement

## Objective

Complete the Agent Brain plugin consolidation and improve skills to 95%+ grade:

1. Remove deprecated `agent-brain-skill/` directory (content now in plugin)
2. Rename `agent-brain-setup` skill to `configuring-agent-brain` (proper naming)
3. Ensure commands and agents properly reference skills
4. Grade and improve both skills to 95%+ using the improving-skills rubric

---

## Current State Analysis

### Duplicate Content Found
- `agent-brain-skill/using-agent-brain/` duplicates `agent-brain-plugin/skills/using-agent-brain/`
- Only unique content: `scripts/query_domain.py` (move to plugin before deletion)

### Naming Convention Issue
- **Current**: `agent-brain-setup` (product-focused)
- **Should be**: `configuring-agent-brain` (action-focused, follows `using-X`, `mastering-X` pattern)

### Current Skill Grades
| Skill | Current Grade | Target |
|-------|---------------|--------|
| using-agent-brain | 82/100 (B) | 95/100 (A) |
| agent-brain-setup | ~70/100 (C) | 95/100 (A) |

### Cross-Reference Analysis
- Commands DO reference skills via `skills:` frontmatter field
- Agents DO reference skills via `skills:` frontmatter field
- This is the correct pattern - no changes needed to cross-references

---

## Deliverables

### 1. Remove Deprecated Directory

**Action**: Delete `agent-brain-skill/` after moving unique content

**Files to move first**:
- `agent-brain-skill/using-agent-brain/scripts/query_domain.py` → `agent-brain-plugin/skills/using-agent-brain/scripts/`

**Then delete**:
- `agent-brain-skill/` (entire directory)

### 2. Rename Setup Skill

**Current**: `agent-brain-plugin/skills/agent-brain-setup/`
**New**: `agent-brain-plugin/skills/configuring-agent-brain/`

**Files to update**:
1. Rename directory
2. Update SKILL.md frontmatter `name:` field
3. Update `marketplace.json` skill path and name
4. Update all commands that reference this skill
5. Update `setup-assistant` agent skill reference

### 3. Improve `using-agent-brain` to 95%

**Current Score**: 82/100 (B)
**Target Score**: 95/100 (A)

**Critical Fixes** (from evaluation):

| Issue | Fix | Points |
|-------|-----|--------|
| Second-person voice | Remove "the user", "Ask the user" | +2 |
| Non-standard `license:` field | Move to `metadata:` | +2 |
| Missing "When Not to Use" | Add scope boundaries section | +1 |
| No counter-examples | Add wrong usage examples | +1 |
| Verbose explanations | Tighten intro paragraphs | +1 |
| Extract Interactive Setup | Move to reference file | +2 |
| **Total Improvement** | | **+9 → 91** |

**Additional improvements for 95%**:
- Add allowed-tools field (+1)
- Enhance checklist format (+1)
- Add more feedback loops (+2)

### 4. Improve `configuring-agent-brain` to 95%

**Estimated Current Score**: ~70/100 (C)

**Issues identified**:
1. Non-standard `license:` at top level (-2)
2. Limited trigger phrases in description (-2)
3. No "When Not to Use" section (-1)
4. Second-person implicit ("your project") (-1)
5. Missing counter-examples (-1)
6. No allowed-tools field (-1)

**Fixes needed**:
| Issue | Fix | Points |
|-------|-----|--------|
| Add 5+ trigger phrases | "install agent brain", "setup", "configure API" | +3 |
| Move `license:` to metadata | Fix frontmatter | +2 |
| Add "When Not to Use" | Scope boundaries | +1 |
| Remove second-person | Fix voice throughout | +2 |
| Add counter-examples | Show common mistakes | +1 |
| Add allowed-tools | Bash, Read | +1 |
| Tighten explanations | Remove verbose intros | +2 |
| **Total Improvement** | | **+12 → ~82** |

**Additional improvements for 95%**:
- Extract detailed troubleshooting to reference (+3)
- Add validation feedback loops (+2)
- Improve workflow clarity (+2)
- Add gerund trigger phrases (+1)

---

## Implementation Order

### Phase 1: Consolidation
1. Move `scripts/query_domain.py` to plugin
2. Delete `agent-brain-skill/` directory
3. Rename `agent-brain-setup/` to `configuring-agent-brain/`
4. Update all cross-references (marketplace.json, commands, agents)

### Phase 2: Improve `using-agent-brain` (82 → 95)
1. Fix frontmatter (`license:` → `metadata:`)
2. Remove second-person voice throughout
3. Add "When Not to Use" section
4. Add counter-examples to search modes
5. Extract "Interactive Setup" to reference
6. Tighten verbose explanations
7. Add `allowed-tools:` field
8. Re-grade to verify 95%+

### Phase 3: Improve `configuring-agent-brain` (70 → 95)
1. Rename in frontmatter to match directory
2. Add 5+ trigger phrases to description
3. Fix `license:` field placement
4. Remove second-person voice
5. Add "When Not to Use" section
6. Add counter-examples
7. Extract troubleshooting to reference
8. Add `allowed-tools:` field
9. Add validation feedback loops
10. Re-grade to verify 95%+

### Phase 4: Verification
1. Re-grade both skills with improving-skills rubric
2. Verify all cross-references work
3. Test skill activation with trigger phrases

---

## File Changes Summary

### Files to Create
```
agent-brain-plugin/skills/using-agent-brain/scripts/query_domain.py
agent-brain-plugin/skills/using-agent-brain/references/interactive-setup.md
agent-brain-plugin/skills/configuring-agent-brain/  (renamed from agent-brain-setup)
```

### Files to Modify
```
agent-brain-plugin/skills/using-agent-brain/SKILL.md
agent-brain-plugin/skills/configuring-agent-brain/SKILL.md
agent-brain-plugin/.claude-plugin/marketplace.json
agent-brain-plugin/commands/agent-brain-config.md
agent-brain-plugin/commands/agent-brain-init.md
agent-brain-plugin/commands/agent-brain-install.md
agent-brain-plugin/commands/agent-brain-setup.md
agent-brain-plugin/commands/agent-brain-verify.md
agent-brain-plugin/agents/setup-assistant.md
```

### Files to Delete
```
agent-brain-skill/  (entire directory - 14 files)
agent-brain-plugin/skills/agent-brain-setup/  (after rename)
```

---

## Cross-Reference Pattern (Best Practices)

### How It Works
1. **Commands** declare `skills:` in frontmatter → Claude loads skill context
2. **Agents** declare `skills:` in frontmatter → Agent has skill knowledge
3. **Skills** are standalone knowledge bases → Referenced by commands/agents

### Current Pattern (Correct)
```yaml
# In command frontmatter
skills:
  - using-agent-brain
  - configuring-agent-brain

# In agent frontmatter
skills:
  - using-agent-brain
```

### Rules
- Commands SHOULD reference relevant skills
- Agents SHOULD reference skills they need
- Commands should NOT reference agents (agents are for proactive behavior)
- Skills should NOT reference commands (skills are knowledge, commands are actions)

---

## Verification Checklist

After implementation:
- [ ] `agent-brain-skill/` directory deleted
- [ ] `configuring-agent-brain/` skill exists with correct name
- [ ] All 5 commands updated to reference `configuring-agent-brain`
- [ ] `setup-assistant` agent references `configuring-agent-brain`
- [ ] `marketplace.json` has correct skill paths
- [ ] `using-agent-brain` grades 95%+ on re-evaluation
- [ ] `configuring-agent-brain` grades 95%+ on re-evaluation
- [ ] All trigger phrases activate correct skills

---

## Success Criteria

| Metric | Target |
|--------|--------|
| `using-agent-brain` grade | ≥95/100 (A) |
| `configuring-agent-brain` grade | ≥95/100 (A) |
| Deprecated files removed | 100% |
| Cross-references valid | 100% |
| Naming conventions followed | 100% |
