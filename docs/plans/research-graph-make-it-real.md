# Plan: Make research-graph real (Layer 1 projector → live Agent Brain wiring)

**Date:** 2026-08-30
**Status (2026-09-03):** Gap A / Phase B item 6 **shipped** in [v10.7.0](https://github.com/SpillwaveSolutions/agent-brain/releases/tag/v10.7.0) (`POST /graph/project`, namespaced `okf:*` types, `DELETE /graph/project?source_tag=`, spawn isolation). **`informs` is not written** — query-only inverse of content-media `Article → draws_from → Finding`; research-graph does not own `Article`. Execution continues in [research-graph `docs/plans/make-it-real.md`](https://github.com/SpillwaveSolutions/research-graph/blob/main/docs/plans/make-it-real.md). This file is historical design context.
**Repos involved:** [SpillwaveSolutions/research-graph](https://github.com/SpillwaveSolutions/research-graph) (primary),
[SpillwaveSolutions/agent-brain](https://github.com/SpillwaveSolutions/agent-brain) (one contained feature — done),
[SpillwaveSolutions/research-knowledge-capture](https://github.com/SpillwaveSolutions/research-knowledge-capture) (contract source, no changes).
**Informed by:** recent work across the OKF family — okf-plugin 0.8.x, okf-agent-graph (AGER) 0.8.x, RKC 0.2.x, okf-forge, okf-agent-graph-ui.

---

## 1. Where research-graph stands today (v0.1.0)

research-graph is deliberately a stub. Its own PRD says: "Stub projector writes
`projection/manifest.json`. Live Kuzu/Chroma wiring is the next ticket." Concretely:

- `scripts/rg_project.py` scans RKC OKF frontmatter under `<root>/research/**`, filters
  `accepted|reviewed`, and writes `projection/manifest.json`. It never touches Chroma, BM25,
  or Kuzu.
- `scripts/rg_ask.py` implements retrieval-ladder steps 1–2 only: ripgrep over the research
  tree (recently landed as PR #2, mirroring okf-plugin's brand-new rg-backed backlinks
  pattern, including the `OKF_RG_PATH`/`fake_rg.py` conventions) and shelling to RKC's
  `rkc_pack.py`. Steps 3–4 print the literal string `"unprojected — run /research-project"`.
- `.work/todo.jsonl` names the two open items: "Wire Agent Brain Chroma + BM25 + Kuzu" and
  "/research-ask live retrieval".
- Five-host packaging (Agent Plugins 1.0, Claude Code, Grok Build, Codex, Cursor) exists and
  has the family's lockstep-version test — that part is already at family standard.
- Known defects: CI runs only `test_plugin.py` (not `test_ask.py`/`test_project.py`), and
  `test_project.py` hard-codes `/workspace/repos/research-knowledge-capture/sample-knowledge`
  so it silently skips everywhere else. `hooks/hooks.json` is an empty PostToolUse list.

## 2. The contract research-graph must satisfy (from RKC, Layer 0)

RKC v0.2.6 is real and battle-tested (its 0.2.1–0.2.6 releases are all hardening from a
2,997-file corpus run). Its PRD fixes the Layer 1 job precisely:

- **L1 owns:** the Chroma + BM25 + Kuzu projector into Agent Brain, and `/research-ask`.
  **L1 owns no nouns.** "Projector stays here until a second consumer needs the Protocol in core."
- **Project only `accepted|reviewed`** nodes (of RKC's 8 nouns: ResearchArea, Subject,
  ResearchTask, SourceDocument, ResearchQuestion, Claim, Evidence, Finding; 12 registered
  rels: `has_subject`, `related_to`, `has_task`, `ingested_from`, `asks`, `answers`,
  `produced`, `asserts`, `evidenced_by`, `contradicts`, `supersedes`, `same_as`).
- **"Do not fork Agent Brain. `GRAPH_USE_LLM_EXTRACTION=false`."** The index must never
  invent nodes or edges; extraction happened once, deterministically, in L0.
- **Citations resolve in OKF, never in the index.** The spine is
  `Finding → asserts → Claim → evidenced_by → Evidence → source-asset + locator`.
  "No Chroma/Kuzu blob citations."
- **Destroying the index is always safe.** Rebuild from `knowledge/research/**`.
- The projector **may expose `informs` as a query-only inverse** of content-media's
  `Article → draws_from → Finding` edge, but never writes edges whose target types it
  doesn't own.
- Retrieval ladder order is fixed: `rg` → `/research-pack` → BM25/Chroma → Kuzu last.

## 3. What Agent Brain already provides (verified in this repo)

The target side is largely done — this is why the wiring is tractable now:

- **Vectors + lexical:** hybrid BM25 + Chroma retrieval via `POST /query`, with
  `file_paths`, `source_types`, `entity_types`, `relationship_types` filters and
  `mode`/`alpha` hybrid controls. Results carry `source` (file path) + `chunk_id`, so hits
  can be mapped back to OKF locators.
- **Ingestion:** `POST /index/add` (folder-based, queued), `DELETE /index` (clear),
  folders add/remove, job queue with status.
- **Graph:** Kuzu-backed property graph (`KuzuPropertyGraphStore` via LlamaIndex, with
  `simple` JSON fallback), `GET /graph/entity/{type}/{id}` returning the entity plus 1-hop
  incoming/outgoing neighbors, gated by `ENABLE_GRAPH_INDEX`.
- **Extraction can be fully disabled:** `GRAPH_DOC_EXTRACTOR="none"` plus
  `GRAPH_USE_LLM_EXTRACTION=false` means no langextract, no LLM extractor — the exact
  posture RKC demands.
- **Instance isolation:** project-mode instances with `AGENT_BRAIN_STATE_DIR`, UDS
  transport, and the `agent-brain` CLI (`init`/`start`/`stop`/`status`) make a dedicated,
  disposable per-knowledge-root index cheap — which is what makes "destroying the index is
  always safe" honest.

## 4. The real gaps

### Gap A — nobody writes typed OKF edges into the graph (the one Agent Brain change)

Agent Brain's graph vocabulary is the 17 SCHEMA-01 entity types (Package…Enum,
DesignDoc…APIDoc, Service…ConfigFile) and 8 relationship predicates (`calls`, `extends`,
`implements`, `references`, `depends_on`, `imports`, `contains`, `defined_in`). None of
RKC's 8 nouns or 12 rels exist there, and with extraction disabled markdown contributes
nothing to the graph at all. There is also no API to ingest *pre-typed* entities/relations
without extraction.

The good news (verified): the Kuzu/simple backends store generic labeled property nodes —
the 17-type limit lives in the Pydantic `Literal` vocabulary and endpoint validation, not
in physical Kuzu tables. Extending it is a models/validation change, not a storage
migration.

**Recommendation:** add a deterministic **projection ingestion path** to agent-brain-server —
`POST /graph/project` accepting explicit typed entities and relations
(`{entities: [{type, id, properties}], relations: [{src, predicate, dst}], source_tag}`),
upsert semantics, delete-by-`source_tag` for rebuilds — with the type/predicate vocabulary
made extensible (a registered-vocabulary setting or namespaced types, e.g. `okf:Claim`),
so SCHEMA-01 code/doc/infra types and OKF research nouns coexist without forking. This
keeps the *projector logic* in the research-graph plugin (per the RKC PRD) while Agent
Brain merely accepts explicit facts. The alternative — a built-in "frontmatter" doc
extractor in Agent Brain — spreads OKF knowledge into core and is not recommended while
research-graph is the only consumer.

`GET /graph/entity/{type}/{id}` validation must accept the extended vocabulary so ladder
step 4 can traverse `Finding → asserts → Claim` paths.

### Gap B — the projector doesn't project (research-graph work)

`rg_project.py` must actually populate the index. Design that fits everything above:

1. **Materialize a projection corpus** under `<root>/projection/corpus/` — a filtered copy
   of only `accepted|reviewed` node bodies (frontmatter preserved), one file per node,
   named by node id. This is what gets handed to `/index/add`. It solves three problems at
   once: the status filter (Agent Brain indexes folders wholesale; draft nodes must never
   reach the index), locator mapping (each projected file records its OKF `path` so query
   hits resolve back to real OKF locators), and rebuildability (delete `projection/` +
   `DELETE /index` = clean slate).
2. **Manifest v2**: keep `projection/manifest.json` as the rebuild record, adding per-node
   `source_hash` (sha256 of the node file) so re-projection is incremental and idempotent —
   the same pattern as RKC's `catalogs/ingest-index.json` O(1) idempotency index (their
   issue #1 fix; learn from it now rather than at 3k files).
3. **Graph projection**: emit RKC's typed `links` as explicit relations to
   `POST /graph/project` (Gap A), tagged `source_tag: research-graph`, plus the
   `informs` query-only inverse. No extraction anywhere.
4. **Instance management**: the projector ensures a per-knowledge-root Agent Brain
   instance (`agent-brain init`/`start` or direct HTTP against `AGENT_BRAIN_URL`), started
   with `GRAPH_DOC_EXTRACTOR=none`, `GRAPH_USE_LLM_EXTRACTION=false`,
   `ENABLE_GRAPH_INDEX=true`, `AGENT_BRAIN_STATE_DIR=<root>/projection/.agent-brain`.
   Server absent/unreachable = report and exit nonzero for `/research-project`; for
   `/research-ask` it is just a missing ladder rung (see Gap C).

### Gap C — the ask ladder stops at step 2 (research-graph work)

`rg_ask.py` steps 3–4 become live:

- **Step 3 (BM25/Chroma):** `POST /query` (hybrid mode) scoped to the projection corpus
  via the existing `file_paths` filter; map each hit's `source`/`chunk_id` back through the
  manifest to `{node_id, okf_path}`. Output cites OKF locators; chunk text may be shown but
  the citation is always the OKF path — never a blob id.
- **Step 4 (Kuzu):** resolve step-3 hit nodes via `GET /graph/entity/okf:<Type>/<id>` and
  walk the spine (`asserts`, `evidenced_by`, `answers`) for typed paths; used for
  "why/how supported" questions and for pulling the citation spine when the packer can't.
- **Missing-server behavior mirrors missing-rg:** "not an error" — the ladder reports the
  rung as unavailable (`index: unreachable — start with /research-project`) and lower rungs
  still answer. This matches the family's fail-soft read path / fail-closed write path
  split.

### Gap D — quality and conventions parity with the recent OKF work

The OKF family's last three weeks set a clear bar (okf-plugin 0.7.x–0.8.1, AGER
0.6.x–0.8.1, RKC 0.2.x). research-graph should match it:

- **CI must run all tests.** Today ci.yml runs `py_compile` + `test_plugin.py` only. Add
  `test_ask.py`, `test_project.py`, and the new projector/ladder tests. Fix
  `test_project.py`'s hard-coded `/workspace/repos/...` path — discover the RKC sibling the
  same way `rg_ask.py` does, or check out RKC in CI the way AGER's quality.yml checks out
  okf-plugin (and pin a *current* tag; AGER's stale `v0.3.2` pin is a documented trap).
- **Test the wire without the server:** fake Agent Brain HTTP fixture (same spirit as
  `tests/fixtures/fake_rg.py`), asserting: draft nodes never reach `/index/add`; rebuild
  after destroy converges to the same manifest; citations resolve to OKF paths.
- **Worklog/WikiTicket SDD adoption:** okf-plugin, AGER, and RKC all run the vendored
  worklog toolchain (ULID-stamped commits enforced by `hooks/commit-msg`, `.work/` ledgers,
  version-lockstep release ritual). research-graph has a bare `.work/todo.jsonl` and no
  hooks. Adopt the same `bin/` + git-hooks setup when the repo starts taking real traffic.
- **E2E acceptance run** against RKC's `sample-knowledge` (fiction corpus, pack root
  `subject.loop-policy.01J8X000000000000000000001`): project → ask "false alert rate" →
  answer cites `evidence.loop-policy…0007`'s locator into the archived source asset.

### Gap E — ecosystem seams (no code now, but decide deliberately)

- **Nobody else in the family knows research-graph exists.** Zero references in okf-plugin,
  AGER, okf-forge, or okf-agent-graph-ui (verified by grep over trees and git history).
  When v0.2 ships, add research-graph/RKC to okf-plugin's family roster docs
  (ONBOARDING.md) — and note RKC's schemas are *not* in `okf_schema.py`'s hardcoded
  sibling-discovery list, which matters for anyone validating a mixed second brain with
  research nouns in it.
- **AGER's `RetrievalBinding backend: hybrid` / `KnowledgeBind query_mode: graph_expand`
  are declared config with no engine anywhere.** research-graph's ask ladder is the natural
  engine behind those bindings. Out of scope for v0.2; record it as the follow-on so the
  two vocabularies don't drift apart.
- **okf-forge visualizes plain OKF markdown directories** (auto-detects `.okf/` /
  `sample-okf/`), so the RKC tree is already viewable there for free — the projection
  gains nothing from a Forge integration and none should be built.
- **Naming collision, docs-only:** "research graph" is also the *name of the sample
  multi-agent loop* in okf-agent-graph (`sample-ager/index.md`, "Sample AGER research
  graph") and okf-agent-graph-ui ("Parallel research graph"). Worth one disambiguating
  line in research-graph's README.

## 5. Sequenced work items

**Phase A — vectors + lexical live (research-graph only; no Agent Brain changes):**
1. Projection corpus writer + manifest v2 (incremental via `source_hash`).
2. Instance management (`init`/`start`/health via CLI or HTTP; env-configurable URL).
3. `/index/add` wiring + `rg_ask` step 3 (`/query` + locator mapping).
4. Test fixtures (fake server), fix `test_project.py` path, wire all tests into CI.
5. Release v0.2.0 (lockstep bump, CHANGELOG, `.work/todo.jsonl` item 2 partially done).

**Phase B — typed graph (agent-brain feature + research-graph consumption):**
6. agent-brain: `POST /graph/project` (explicit entities/relations, upsert,
   delete-by-source_tag) + extensible/namespaced type vocabulary + `/graph/entity`
   validation update. Spec'd via the normal speckit flow in this repo.
7. research-graph: project the 12 rels + `informs` inverse; `rg_ask` step 4 typed paths.
8. E2E acceptance run against `sample-knowledge`; release v0.3.0.

**Phase C — family integration:**
9. Worklog/WikiTicket adoption, ULID commit hooks, family roster docs, README
   disambiguation note, AGER retrieval-binding alignment ticket.

## 6. Acceptance criteria ("real" means)

- `/research-project` on RKC `sample-knowledge` populates a live per-root Agent Brain
  instance (Chroma + BM25 + Kuzu), projecting exactly the `accepted|reviewed` nodes, with
  zero LLM/langextract extraction.
- `/research-ask "false alert rate"` walks all four rungs and answers with citations that
  resolve `Finding → Claim → Evidence → source-asset locator` in the OKF tree — never a
  vector or graph blob.
- `DELETE` the index + delete `projection/` + re-run `/research-project` converges to an
  identical manifest (destroy is always safe, rebuild is deterministic).
- Draft/rejected/superseded nodes are provably absent from the index (test-enforced).
- Missing rg, missing RKC, or missing server each degrade one rung without failing the
  ladder.
- CI runs the full test suite on every push, including the projector and ladder tests.
