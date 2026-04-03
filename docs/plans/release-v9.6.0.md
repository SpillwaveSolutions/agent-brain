# Plan: Prepare v9.6.0 Release Tag

Goal: Prepare the next local release/tag from the current `main` state by bumping package versions to `9.6.0`, updating release notes, and creating a local annotated Git tag.

Steps:
1. Update versioned package metadata in both Poetry projects and their `__version__` modules.
2. Align the CLI package dependency on `agent-brain-rag` to `^9.6.0`.
3. Add a `9.6.0` changelog entry summarizing the runtime parity harness foundation work.
4. Verify all version references are consistent.
5. Commit the release prep as `chore(release): bump version to 9.6.0`.
6. Create an annotated local tag `v9.6.0`.

Scope limits:
- Do not push commits or tags.
- Do not publish a GitHub release or PyPI artifacts.
- Do not mark the broader planning milestone as fully shipped in `.planning/` docs.
