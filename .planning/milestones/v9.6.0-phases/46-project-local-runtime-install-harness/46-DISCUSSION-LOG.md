# Phase 46: Project-Local Runtime Install Harness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 46-project-local-runtime-install-harness
**Areas discussed:** integration project layout, install verification, failure reporting, canonical references

---

## Integration project layout

| Option | Description | Selected |
|--------|-------------|----------|
| A | Single shared root with runtime-specific subdirectories and shared logs | |
| B | Separate per-runtime directories to keep workspaces fully isolated | ✓ |
| C | Hybrid shared root with per-runtime subfolders plus shared tools | |
| D | Custom structure | |

**User's choice:** Option B, with runtime-specific directories under a git-ignored `e2e_workdir/` root.
**Notes:** User clarified that the runtime workspaces should live under `e2e_workdir/` so the area stays out of Git. User also requested a cleanup folder in each runtime workspace.

---

## Install verification

| Option | Description | Selected |
|--------|-------------|----------|
| A | Check expected directories/files and converter output only | |
| B | Add a lightweight verification script for files and JSON output | |
| C | Probe the installed runtime with a dry headless JSON-returning command | |
| D | Run A, B, and C sequentially | ✓ |

**User's choice:** Option D.
**Notes:** Verification should be thorough and layered: confirm generated structure, run helper checks, then require a dry runtime probe before deeper execution continues.

---

## Failure reporting

| Option | Description | Selected |
|--------|-------------|----------|
| A | `failure.log` only | |
| B | Structured JSON only | |
| C | Both log and JSON with remediation hints | ✓ |
| D | Exit-code-first with minimal logging | |

**User's choice:** Option C.
**Notes:** Failures should be readable by humans and automation. Remediation hints are required for cases like missing runtime binaries.

---

## Canonical references

| Option | Description | Selected |
|--------|-------------|----------|
| A | Use roadmap phase definition | ✓ |
| B | Use milestone requirements | ✓ |
| C | Use runtime install documentation | ✓ |
| D | Use GSD workflow docs relevant to discussion/planning/verification | ✓ |

**User's choice:** Asked the agent to read the GSD/runtime docs and pick the best canonical references.
**Notes:** Selected refs were derived from the phase definition and the existing runtime parity harness: `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `e2e-cli/README.md`, `e2e-cli/lib/runtime_parity.sh`, and the relevant GSD workflow docs.

---

## the agent's Discretion

- Final helper/script names inside each runtime workspace.
- Exact JSON schema fields beyond the required runtime, error type, details, and remediation hints.
- Exact placement rules for the `cleanup/` helper within each runtime workspace.

## Deferred Ideas

None.
