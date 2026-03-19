---
created: 2026-03-19T03:07:48.866Z
title: Add "AST for code + LangExtract for docs" as a first-class GraphRAG option in agent-brain-config wizard Step 7
area: tooling
files:
  - agent-brain-plugin/commands/agent-brain-config.md:544-690
---

## Problem

The `/agent-brain-config` wizard Step 7 (GraphRAG configuration) offers three options:
1. Disabled
2. Enabled (Simple / JSON persistence)
3. Enabled + Kuzu

After choosing option 2 or 3, a *separate* sub-question asks about extraction mode
(AST / LLM / LangExtract). The combination "AST for code chunks + LangExtract for
document/prose chunks" is supported by the server (`GRAPH_USE_CODE_METADATA=true` +
`GRAPH_DOC_EXTRACTOR=langextract`) but is buried in the sub-question flow and not
obvious to users.

A user selecting option 2 who wants the best mixed-repo setup has to know to:
- Pick "LangExtract" from the sub-question
- Also know that `GRAPH_USE_CODE_METADATA=true` is needed alongside it

This combination is the most powerful and practical setup for projects with both
code and documentation, but it's completely non-discoverable from the wizard UI.

## Solution

Three approaches (in order of preference):

**Approach A — Add 4th top-level option (minimal change)**
Add directly to the Step 7 GraphRAG question:
```
4. AST + LangExtract (Recommended for mixed repos)
   Extracts code relationships via AST + semantic entities from docs via your
   summarization provider. Best of both — no extra API key needed.
```
Sets: `GRAPH_USE_CODE_METADATA=true` + `GRAPH_DOC_EXTRACTOR=langextract`

**Approach B — Split into two questions**
Q1: Store type (disabled / simple / kuzu)
Q2: Extraction mode (AST only / LangExtract only / AST + LangExtract / LLM)
Makes extraction mode a first-class concern, but adds one more wizard step.

**Approach C — Make combined mode the new recommended default**
Change option 2 label from "Enabled (AST/Code)" to "Enabled - AST + LangExtract
(Recommended for mixed repos)". Pure AST-only moves to an advanced/custom option.
Fewest prompts, best defaults, most opinionated.

## Notes

- The feature is already implemented in the server — this is purely a wizard UX fix
- Must check if LangExtract is installed before presenting option (guide install if not)
- The combined config YAML:
  ```yaml
  graphrag:
    enabled: true
    store_type: "simple"
    use_code_metadata: true
  ```
  Plus env: `GRAPH_DOC_EXTRACTOR=langextract`
