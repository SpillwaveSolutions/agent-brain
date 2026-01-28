# Requirements Quality Checklist: Multi-Instance Architecture

**Purpose**: Validate completeness, clarity, consistency, and coverage of requirements across spec.md, plan.md, data-model.md, contracts/api-changes.yaml, and quickstart.md
**Created**: 2026-01-27
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)
**Depth**: Standard | **Audience**: PR Reviewer | **Focus**: Architecture/Lifecycle, API/Contracts

## Requirement Completeness

- [ ] CHK001 Are storage path migration requirements defined for users upgrading from the current ./chroma_db and ./bm25_index layout? FR-016 says "re-indexing expected" but no migration UX is specified. [Completeness, Spec FR-016]
- [ ] CHK002 Are requirements defined for what happens when doc-serve start is run but the server binary/package is not installed? [Gap]
- [ ] CHK003 Are log rotation or log size management requirements specified for per-project state_dir/logs/ directory? [Gap]
- [ ] CHK004 Are requirements defined for the doc-serve list command behavior when some instances are on remote/NFS filesystems where PID checks may be unreliable? [Gap]
- [ ] CHK005 Are configuration precedence requirements (FR-009) documented with concrete examples showing override behavior for each level (CLI > env > project config > global config > defaults)? [Completeness, Spec FR-009]
- [ ] CHK006 Are requirements specified for .gitignore management - does init automatically add runtime files to .gitignore or is this manual? [Gap, Quickstart Verification Checklist]
- [ ] CHK007 Are requirements defined for the server startup timeout - how long does the CLI start command wait for the health endpoint before reporting failure? [Gap]
- [ ] CHK008 Are requirements defined for what happens when doc-serve stop is called but the process does not exit after SIGTERM? (escalation to SIGKILL, timeout) [Gap, Spec FR-010]

## Requirement Clarity

- [ ] CHK009 Is "collision-free port" in US1 quantified - does it mean zero-conflict guarantee (port 0 binding) or best-effort? The spec says "collision-free" but plan says "bind to port 0" - are these equivalent? [Clarity, Spec US1 vs Plan Decision 1]
- [ ] CHK010 Is the term "state directory" consistently defined? Spec uses "project's own directory structure" (FR-003), plan uses repo/.claude/doc-serve/, data-model uses "state directory" - are all three referring to the same path? [Clarity, Spec FR-003, Plan Decision 4]
- [ ] CHK011 Is "crash recovery within 5 seconds" (SC-003) measured from user action (running start) or from automatic detection? The spec does not define the trigger. [Clarity, Spec SC-003]
- [ ] CHK012 Is "recognized marker" in US2 scenario 3 explicitly enumerated? The plan lists .claude/ and pyproject.toml, but the spec says "standard project markers" without listing them. [Clarity, Spec US2, Plan Decision 2]
- [ ] CHK013 Is the instance_id format specified (e.g., ds_3f0f1c in data-model.md) - what hash input produces it, and what is the prefix convention? [Clarity, Data-Model RuntimeState]
- [ ] CHK014 Is "health endpoint responds" as the liveness criterion quantified with a timeout threshold? How long before a health check is considered failed? [Clarity, Spec FR-006]

## Requirement Consistency

- [ ] CHK015 Do the runtime.json field requirements align between spec (FR-004: "machine-readable discovery file"), data-model (RuntimeState entity), and contracts (runtime_json_project schema)? Are all three in agreement on required fields? [Consistency, Spec FR-004, Data-Model RuntimeState, Contracts runtime_json_project]
- [ ] CHK016 Does the health endpoint response schema in contracts (health_response_v2) align with the health requirements in spec (FR-013: "expose mode information")? The contracts add instance_id, project_id, active_projects - are these required by the spec? [Consistency, Spec FR-013, Contracts health_response_v2]
- [ ] CHK017 Are the CLI commands in quickstart.md (doc-serve init/start/status/stop/list) consistent with the spec FR-011 and FR-012 requirements? Quickstart shows doc-serve index and doc-serve query - are these existing commands or new ones? [Consistency, Quickstart Per-Project Mode, Spec FR-011]
- [ ] CHK018 Do the plan's 4 implementation phases align with the spec's 4 user story priorities (P1-P4)? Phase 1 is "State Directory Decoupling" which is not a user story - is this intentional? [Consistency, Plan Phases, Spec User Stories]
- [ ] CHK019 Is the shared daemon port (45123 in data-model SharedConfig) consistent with the port 0 binding strategy for project mode? Are both allocation strategies documented together? [Consistency, Data-Model SharedConfig, Research Decision 1]

## Acceptance Criteria Quality

- [ ] CHK020 Can SC-001 ("5 or more projects concurrently without port conflicts or index cross-contamination") be objectively measured? Is "cross-contamination" defined with a specific test? [Measurability, Spec SC-001]
- [ ] CHK021 Can SC-002 ("same server instance 100% of the time") be tested given that symlinks, mount points, and network filesystems can produce edge cases? Is the scope of "100%" bounded? [Measurability, Spec SC-002]
- [ ] CHK022 Can SC-004 ("discover in under 1 second") be measured - does this include health check latency or just file read time? [Measurability, Spec SC-004]
- [ ] CHK023 Can SC-008 ("3 steps: init, start, query") be verified - does "query" require prior indexing, making it effectively 4+ steps? [Measurability, Spec SC-008]
- [ ] CHK024 Are acceptance scenarios in US1-US4 written with specific enough Given/When/Then clauses to derive automated tests without interpretation? [Measurability, Spec US1-US4]

## Scenario Coverage

- [ ] CHK025 Are requirements defined for concurrent start attempts on the same project from different terminals? FR-007 says "exclusive lock" but does not specify the user-facing error message or behavior. [Coverage, Spec FR-007]
- [ ] CHK026 Are requirements defined for what happens when doc-serve start is run in a directory that is a subdirectory of an already-running project? Should it discover the parent or start a new instance? [Coverage, Edge Case 4 implied]
- [ ] CHK027 Are requirements defined for disk space exhaustion during indexing? The state directory could fill up. [Gap]
- [ ] CHK028 Are requirements defined for the transition path from per-project to shared mode (Edge Case 6)? The spec says "MUST NOT mix state" but does not describe the user workflow. [Coverage, Spec Edge Case 6]
- [ ] CHK029 Are requirements defined for what happens when the user home directory is unavailable (~/.doc-serve/) in shared daemon mode? [Gap, Data-Model SharedConfig]
- [ ] CHK030 Are requirements defined for the behavior when runtime.json is manually edited or corrupted? [Gap]

## Edge Case Coverage

- [ ] CHK031 Is Edge Case 1 (port reuse after OS assignment) addressed with specific validation requirements beyond "validate the health endpoint"? What if the health endpoint responds but belongs to a different process? [Edge Case, Spec Edge Case 1]
- [ ] CHK032 Is Edge Case 4 (project moved after indexing) defined with a detection mechanism? How does the system detect the mismatch between stored project_root and actual location? [Edge Case, Spec Edge Case 4]
- [ ] CHK033 Is Edge Case 5 (different user process) addressed with requirements for multi-user environments? Does os.kill(pid, 0) work across users on macOS/Linux? [Edge Case, Spec Edge Case 5]
- [ ] CHK034 Are requirements defined for maximum number of concurrent instances? SC-001 says "5 or more" but is there an upper bound before resource exhaustion? [Edge Case, Spec SC-001]
- [ ] CHK035 Are requirements defined for behavior when fcntl.flock() is not available (e.g., certain NFS mounts, Windows via WSL)? Research Decision 3 says "Unix" but the spec targets "macOS/Linux". [Edge Case, Research Decision 3]

## Non-Functional Requirements

- [ ] CHK036 Are performance requirements specified for server startup time (from start command to health endpoint ready)? SC-003 covers crash recovery but not cold start. [Gap]
- [ ] CHK037 Are memory/resource requirements specified per instance? If 5+ instances run concurrently (SC-001), what is the expected resource footprint? [Gap]
- [ ] CHK038 Are security requirements specified for runtime.json file permissions? It contains the server URL and PID - should it be readable only by the owner? [Gap]
- [ ] CHK039 Are backward compatibility requirements defined for the existing CLI (doc-svr-ctl) - will doc-svr-ctl status still work with the old DOC_SERVE_URL env var? [Gap]
- [ ] CHK040 Are observability requirements beyond FR-013 (health endpoint) specified? Is structured logging format defined? Are log levels documented? [Gap, Plan Constitution IV]

## Dependencies & Assumptions

- [ ] CHK041 Is the assumption "localhost binding by default" validated against the shared daemon use case where multiple users on the same machine might need access? [Assumption, Spec Assumptions]
- [ ] CHK042 Is the assumption that git is available on the system documented as a soft dependency? Research Decision 2 falls back gracefully, but the spec does not mention this. [Assumption, Research Decision 2]
- [ ] CHK043 Are the dependencies between user stories explicitly documented in the spec? The plan implies US3 and US4 depend on US1, but the spec presents them as independent. [Dependency, Spec US1-US4, Plan Phases]
- [ ] CHK044 Is the dependency on FastAPI app.state for singleton replacement documented as an architectural requirement? The spec does not mention it but the plan relies on it. [Dependency, Research Decision 6]

## Ambiguities & Conflicts

- [ ] CHK045 Is there a conflict between FR-003 ("state travels with the project") and the shared daemon mode where state lives in ~/.doc-serve/projects/? In shared mode, state does NOT travel with the project. [Conflict, Spec FR-003 vs FR-008]
- [ ] CHK046 Is the scope of "all runtime artifacts" in FR-010 explicitly enumerated? The data-model lists runtime.json, doc-serve.lock, doc-serve.pid - but what about log files and index data? [Ambiguity, Spec FR-010, Data-Model LockState]
- [ ] CHK047 Does "no automated data migration" (FR-016) conflict with SC-008 "3-step onboarding"? Existing users must re-index, which adds steps beyond init/start/query. [Conflict, Spec FR-016 vs SC-008]
- [ ] CHK048 Is there ambiguity in whether doc-serve init is required before doc-serve start? The quickstart shows init first, but the spec says config is "optional" (Assumption in data-model). [Ambiguity, Quickstart 1, Data-Model ProjectConfig]

## Notes

- Check items off as completed: [x]
- Add comments or findings inline
- Items are numbered sequentially (CHK001-CHK048) for easy reference
- References use: [Spec section], [Plan section], [Data-Model entity], [Research Decision N], [Contracts schema], [Quickstart section]
- [Gap] = requirement not documented anywhere; [Conflict] = requirements contradict; [Ambiguity] = requirement unclear
