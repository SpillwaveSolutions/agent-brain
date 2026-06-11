# Plugin Skill Grades — June 2026

Evaluation of the two Agent Brain plugin skills against the `improving-skills`
5-pillar rubric (PDA 30 / Ease 25 / Spec 15 / Style 10 / Utility 20, ±15 modifiers).
Graded 2026-06-10 against package state v10.3.0.

| Skill | Score | Grade |
|-------|-------|-------|
| `configuring-agent-brain` | 73/100 | C |
| `using-agent-brain` | 80/100 | B |

---

## configuring-agent-brain — 73/100 (C)

| Pillar | Score | Notes |
|--------|-------|-------|
| Progressive Disclosure (PDA) | 20/30 | Good layering (SKILL.md → references/), but the body is long (704 lines) and front-loads provider tables that could live in references. Navigation contents block is solid. |
| Ease of Use | 21/25 | Rich trigger list in `description`; clear Quick Setup A/B split. Loses points for no MCP/UDS triggers and a stale `version: 7.0.0`. |
| Spec Compliance | 12/15 | Valid frontmatter, good naming. Stale `version`/`last_validated`; install examples use bare `pip` while `references/installation-guide.md` recommends pipx/uv (internal contradiction). |
| Writing Style | 9/10 | Objective, imperative, good counter-examples. |
| Utility | 14/20 | Strong verification checklists and troubleshooting. **Zero coverage of the MCP package** (`agent-brain-ag-mcp`) or UDS transport — a whole shipped surface is undocumented. Stale `3.0.0` version example. |
| Modifiers | −3 | −3 stale version metadata + version example drift. |

### Top findings
1. **No MCP coverage.** The `agent-brain-mcp` server (PyPI `agent-brain-ag-mcp`) ships in 10.x and is invisible here. Add an install + client-config section.
2. **pip vs pipx/uv contradiction.** SKILL.md Quick Setup uses bare `pip`; `installation-guide.md` leads with pipx (recommended) / uv. Reconcile by pointing at the isolated installers.
3. **Stale version metadata.** `version: 7.0.0`, `last_validated: 2026-03-19`, line ~192 `e.g., 3.0.0`, line ~530 `7.0.0+` — all predate v10.3.0.

---

## using-agent-brain — 80/100 (B)

| Pillar | Score | Notes |
|--------|-------|-------|
| Progressive Disclosure (PDA) | 24/30 | Excellent: tight 423-line body, mode tables, references/ for depth. |
| Ease of Use | 22/25 | Outstanding trigger coverage in `description`; clear mode-selection guide with counter-examples. Stale `version: 7.0.0`. |
| Spec Compliance | 12/15 | Valid frontmatter; stale version/date. Server-management section mixes bare CLI and `/agent-brain:*` slash-command forms without explaining the relationship. |
| Writing Style | 9/10 | Crisp, example-driven. |
| Utility | 15/20 | Very strong. One correctness bug: **threshold default inconsistency** — Mode Parameters table says default `0.3` (correct, matches `query.py:81`) but Best Practices #2 says "Start at 0.7". Misleads users into over-filtering. |
| Modifiers | −2 | −2 stale version metadata. |

### Top findings
1. **Threshold contradiction.** Reconcile Best Practices #2 with the documented `0.3` default.
2. **Stale version metadata.** `version: 7.0.0`, `last_validated: 2026-03-19`.
3. **No MCP/IDE-client note.** The `description` lists runtimes (Claude Code, OpenCode, Gemini CLI) but not MCP-aware IDE clients now served by `agent-brain-mcp`.

---

## Cross-cutting reference staleness

- `references/version-management.md` — version history frozen at `7.0.0` (2026-03); dependency pins use `>=3.0.0,<4.0.0` and `^3.0.0` (should be `>=10.0.0,<11.0.0` / `^10.0.0`).
- `scripts/query_domain.py:28` — legacy `DOC_SERVE_URL` env fallback (pre-rename name); `AGENT_BRAIN_URL` is canonical.

---

## Fixes applied in this PR

- Both SKILL.md frontmatter → `version: 10.3.0`, `last_validated: 2026-06-10`.
- `configuring-agent-brain`: added an **MCP server** section (`agent-brain-ag-mcp` install + client config JSON + UDS/transport note); reconciled install guidance toward pipx/uv; fixed the `3.0.0`/`7.0.0+` version examples.
- `using-agent-brain`: reconciled the threshold Best Practice with the `0.3` default.
- `version-management.md`: refreshed version history + dependency pins to the 10.x line.
- `query_domain.py`: dropped the legacy `DOC_SERVE_URL` fallback.

## JSON

```json
{
  "evaluated": "2026-06-10",
  "package_version": "10.3.0",
  "skills": [
    {
      "name": "configuring-agent-brain",
      "score": 73,
      "grade": "C",
      "pillars": {"pda": 20, "ease": 21, "spec": 12, "style": 9, "utility": 14},
      "modifiers": -3,
      "top_findings": [
        "No MCP/UDS coverage (agent-brain-ag-mcp)",
        "pip vs pipx/uv contradiction with installation-guide.md",
        "Stale version metadata (7.0.0 / 3.0.0 examples)"
      ]
    },
    {
      "name": "using-agent-brain",
      "score": 80,
      "grade": "B",
      "pillars": {"pda": 24, "ease": 22, "spec": 12, "style": 9, "utility": 15},
      "modifiers": -2,
      "top_findings": [
        "Threshold default inconsistency (0.3 table vs 0.7 best-practice)",
        "Stale version metadata (7.0.0)",
        "No MCP/IDE-client note in description"
      ]
    }
  ]
}
```
