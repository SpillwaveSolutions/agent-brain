# Phase 37: Complete Link Verification & Audit Metadata - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning
**Source:** Codebase analysis + roadmap gap closure

<domain>
## Phase Boundary

Phase 37 closes the remaining documentation quality gaps from the v10.0 milestone audit. It has four concrete deliverables:

1. **Fix the `is_url('#')` bug** in `scripts/check_doc_links.py` so same-file anchor links are actually verified instead of silently skipped
2. **Fix broken ToC anchors** in `docs/DEVELOPERS_GUIDE.md` (5 anchors point to non-existent headings)
3. **Stamp SKILL.md root files** with `last_validated` frontmatter (2 files need it)
4. **Write VERIFICATION.md files** for all 5 milestone phases (29, 30, 31, 32, 33) — all are missing

This phase is documentation-only. No Python package code changes. No tests needed beyond running the existing link checker.

</domain>

<decisions>
## Implementation Decisions

### Bug: is_url('#') in scripts/check_doc_links.py

The bug is at line 99:

```python
def is_url(target: str) -> bool:
    """Check if a link target is an external URL or special link."""
    return target.startswith(("http://", "https://", "mailto:", "#", "ftp://"))
```

`"#heading".startswith("#")` returns `True`, so `is_url("#heading")` returns `True`. At line 136, `if is_url(target): continue` skips the link before reaching the anchor-checking code at line 140. The anchor check at line 140 is therefore dead code for any `#`-prefixed target.

**Fix:** Remove `"#"` from the `is_url` tuple. The anchor-handling block at line 140 correctly handles same-file anchors with verification — it just needs `is_url` to stop intercepting them first.

```python
def is_url(target: str) -> bool:
    """Check if a link target is an external URL or special link."""
    return target.startswith(("http://", "https://", "mailto:", "ftp://"))
```

After this fix, the existing code at lines 140-151 handles anchor checking:
- `link_count` is incremented
- `extract_headings(filepath)` is called
- If the anchor is not in headings, a broken link entry is added

**No other logic changes needed.**

### Broken ToC Anchors in docs/DEVELOPERS_GUIDE.md

Five ToC entries point to anchors that don't exist in the document:

| ToC anchor | Does not match any heading |
|---|---|
| `#quick-start` | Heading is `### Quick Start for Developers` → slug: `quick-start-for-developers` |
| `#development-workflow` | No heading with this text exists |
| `#code-style` | No heading with this text exists |
| `#contributing` | No heading with this text exists |
| `#adding-support-for-new-languages` | Heading is `### Step-by-Step: Adding a New Language` → slug: `step-by-step-adding-a-new-language` |

**Fix approach:** Update the ToC to use correct anchors OR add the missing headings. Preferred: update ToC anchors to match existing headings (minimal change). For missing sections (development-workflow, code-style, contributing), add stub headings if the content exists elsewhere or remove the ToC entry if the section is truly absent.

Check the full document to determine whether content exists under different headings before deciding to add stubs vs. fix anchors.

### SKILL.md Audit Metadata

Two SKILL.md files need `last_validated` frontmatter added to the `metadata:` block:

**`agent-brain-plugin/skills/using-agent-brain/SKILL.md`** — current `metadata:` block is empty:
```yaml
metadata:
```

**`agent-brain-plugin/skills/configuring-agent-brain/SKILL.md`** — has `metadata:` with version/category/author but no `last_validated`:
```yaml
metadata:
  version: 7.0.0
  category: ai-tools
  author: Spillwave
```

**Fix:** Add `last_validated: 2026-03-19` to the `metadata:` block of both files. For `using-agent-brain/SKILL.md`, also add standard fields (version, category, author) to bring it in line with `configuring-agent-brain/SKILL.md`.

### VERIFICATION.md Files for Phases 29–33

All 5 milestone phases completed execution but have no VERIFICATION.md. These need to be written from the SUMMARY.md files and ROADMAP.md success criteria.

**Files to create:**
- `.planning/phases/29-cli-api-documentation/29-VERIFICATION.md`
- `.planning/phases/30-configuration-documentation/30-VERIFICATION.md`
- `.planning/phases/31-user-guides/31-VERIFICATION.md`
- `.planning/phases/32-plugin-documentation/32-VERIFICATION.md`
- `.planning/phases/33-cross-references-metadata/33-VERIFICATION.md`

**Structure:** Each VERIFICATION.md should confirm the phase goal was achieved by verifying each success criterion from ROADMAP.md against the current codebase state.

### Claude's Discretion

- Whether to add stub headings vs. fix ToC anchor targets in DEVELOPERS_GUIDE.md (check what content exists)
- Exact `version` and `category` values for `using-agent-brain/SKILL.md` metadata (match the other SKILL.md)
- VERIFICATION.md format: follow the gsd template structure (phase, plan, subsystem, provides, requirements-completed)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Link Checker Script
- `scripts/check_doc_links.py` — The script with the bug; understand full logic before touching

### Affected Documentation Files
- `docs/DEVELOPERS_GUIDE.md` — Has broken ToC anchors (lines 11-20 are the ToC)
- `agent-brain-plugin/skills/using-agent-brain/SKILL.md` — Needs `last_validated` frontmatter
- `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` — Needs `last_validated` frontmatter

### Phase Plans and Summaries (for VERIFICATION.md content)
- `.planning/phases/29-cli-api-documentation/29-01-SUMMARY.md`
- `.planning/phases/29-cli-api-documentation/29-02-SUMMARY.md`
- `.planning/phases/30-configuration-documentation/30-01-SUMMARY.md`
- `.planning/phases/30-configuration-documentation/30-02-SUMMARY.md`
- `.planning/phases/31-user-guides/` — read all SUMMARY.md files
- `.planning/phases/32-plugin-documentation/` — read all SUMMARY.md files
- `.planning/phases/33-cross-references-metadata/33-01-SUMMARY.md`
- `.planning/phases/33-cross-references-metadata/33-02-SUMMARY.md`
- `.planning/ROADMAP.md` — Phase 29–33 success criteria (source of truth for VERIFICATION.md)

</canonical_refs>

<specifics>
## Specific Ideas

### Verification after fix
After fixing `is_url`, run the link checker to see what previously-silently-skipped anchors are now broken:
```bash
python3 scripts/check_doc_links.py | python3 -m json.tool
```

### Known broken anchors (pre-fix baseline)
The DEVELOPERS_GUIDE.md ToC currently has 5 broken anchors:
- `#quick-start` (should be `#quick-start-for-developers`)
- `#development-workflow` (no matching heading)
- `#code-style` (no matching heading)
- `#contributing` (no matching heading)
- `#adding-support-for-new-languages` (should be `#step-by-step-adding-a-new-language`)

### SKILL.md target state for using-agent-brain
```yaml
metadata:
  version: 1.0.0
  category: ai-tools
  author: Spillwave
  last_validated: 2026-03-19
```

</specifics>

<deferred>
## Deferred Ideas

- Adding the link checker to CI/pre-push pipeline (AUTODOC-02) — out of scope for this phase
- Fixing broken links discovered by the link checker in other files — only DEVELOPERS_GUIDE.md ToC is in scope

</deferred>

---

*Phase: 37-complete-link-verification-audit-metadata*
*Context gathered: 2026-03-19*
