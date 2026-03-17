# Generic Prompt: Documentation Accuracy Audit Phase

**Type:** Reusable phase template
**Created:** 2026-03-16
**Use with:** Any project milestone — tool-agnostic, language-agnostic, repo-agnostic

---

## What This Phase Is

This phase performs a **systematic accuracy audit of all documentation** in the repository.

It ensures that documentation is **consistent with the current implementation**, including:

* CLI commands
* configuration schemas
* APIs
* examples
* file paths
* installation instructions
* feature descriptions

This phase acts as the **quality gate before release**.

---

## Core Principle

Documentation must be validated against **real sources of truth**, not other documentation.

Typical sources of truth include:

* CLI `--help` output
* source code definitions
* configuration schema files
* API specifications
* actual program behavior
* executable validation commands

The validation chain should look like:

```
source code
    ↓
CLI/help/schema output
    ↓
documentation
```

Documentation must always be the **final consumer**, not the source.

---

## Requirements

### DOC-AUDIT-01

All documentation files must be cross-checked against the current source code and CLI behavior.

### DOC-AUDIT-02

Any stale or incorrect information must be corrected across all documentation.

This includes:

* outdated command names
* incorrect flags or options
* outdated configuration field names
* incorrect file paths
* broken links
* inconsistent descriptions across documents
* outdated version annotations

---

## Scope of Audit

Audit **all documentation artifacts**, including:

Typical locations include:

```
docs/
docs/guides/
docs/reference/
docs/features/
docs/api/
```

Also include any documentation embedded in:

```
SKILL.md
AGENTS.md
README.md
templates/
examples/
assets/
schema docs
```

Typical file types:

```
*.md
*.yaml
*.yaml.template
*.json
*.json.schema
*.examples
```

---

## Verification Strategy

Use the following structured verification process.

### 1. Build the project

Ensure the current codebase builds successfully.

Example:

```
cargo build
npm build
make build
```

(or equivalent for the project)

---

### 2. Validate CLI behavior

Run the CLI help output for the root command and all subcommands.

Example:

```
project --help
project <command> --help
```

Verify:

* command names
* flags
* options
* argument formats
* examples

Important:
Validate the CLI help output against the **source code definitions** before using it as the documentation reference.

---

### 3. Cross-check docs against implementation

For each documentation file:

Verify that:

* commands match actual CLI commands
* flags match actual CLI flags
* configuration field names match source schemas
* API field names match actual models
* examples reflect current behavior
* install instructions match real install paths
* code snippets compile or execute if applicable

---

### 4. Validate examples

Extract any examples from documentation and test them.

Examples include:

* configuration files
* YAML examples
* JSON examples
* CLI command examples
* API payloads

Run them through the project's validation tools when possible.

Examples:

```
project validate example.yaml
project lint config.yaml
project test example.json
```

---

### 5. Verify cross references

Check that:

* links between docs resolve correctly
* referenced files exist
* anchors are correct
* referenced commands or features exist

---

### 6. Fix documentation in-place

Corrections should be applied directly to the documentation.

Recommended workflow:

* one commit per file
* small, atomic changes
* clear commit messages

Example:

```
docs: fix outdated CLI flag in config-guide.md
docs: update install paths in quickstart.md
docs: correct schema field names in api-reference.md
```

---

### 7. Add validation metadata

Add simple frontmatter to audited documentation files where appropriate.

Example:

```
---
last_modified: 2026-03-16
last_validated: 2026-03-16
---
```

This allows future audits to identify when documentation was last verified.

---

## Staleness Signals to Hunt

During the audit, explicitly look for common sources of documentation drift:

* renamed commands or binaries
* mismatched CLI flags
* configuration fields renamed in code
* outdated file paths or install directories
* examples referencing deprecated behavior
* version annotations that are no longer correct
* inconsistent explanations across documents
* references to removed features

These issues frequently appear after:

* major renames
* feature expansions
* CLI refactors
* schema changes
* installation changes

---

## Fix Strategy

When discrepancies are found:

* correct documentation immediately
* do not defer fixes to later phases
* rewrite sections if necessary
* maintain internal consistency across documents

Documentation should leave this phase **fully accurate and internally consistent**.

---

## Expected Outcome

After this phase:

* all documentation reflects the current behavior of the software
* examples are verified to work
* CLI documentation matches actual CLI behavior
* configuration schemas match source definitions
* cross references between docs are correct
* documentation is internally consistent

This phase serves as the **final documentation verification step before release**.

---

## Deliverables

At the end of the phase:

* all documentation files have been audited
* incorrect content has been corrected
* validation metadata has been added
* commit history clearly shows documentation fixes

The project documentation should now be considered **release-quality**.

---

## Optional Best Practice

Treat documentation auditing the same way you treat testing.

Documentation audits should occur:

* after major feature additions
* after CLI changes
* after schema updates
* before release milestones

This prevents documentation drift and ensures users can rely on documentation as an accurate guide.

---

## LLM-Ready Short Prompt (~12 lines)

```
Perform a documentation accuracy audit for this project.

Cross-check all docs (docs/, README.md, SKILL.md, AGENTS.md, templates/)
against the actual source of truth: CLI --help output, source code definitions,
configuration schemas, and API specs.

Fix any stale command names, incorrect flags, outdated file paths, broken links,
or inconsistent descriptions. Validate examples by running them where possible.

Workflow: build project → run CLI --help → cross-check each doc file →
fix in-place → atomic commits per file.

Add last_validated frontmatter to audited files.
Documentation must be release-quality when this phase completes.
```
