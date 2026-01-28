# Research: Consolidate Spec Directories to .speckit/

**Branch**: `108-speckit-consolidation` | **Date**: 2026-01-27

## Summary

No unknowns or NEEDS CLARIFICATION items exist for this feature. The consolidation involves moving files and updating path references — all technologies and approaches are well-understood.

## Decisions

### D1: Use `git mv` for file moves

- **Decision**: Use `git mv` instead of plain `mv` + `git add`
- **Rationale**: `git mv` ensures git tracks the operation as a rename, preserving blame history and enabling clean `git log --follow` across the move
- **Alternatives considered**: Plain filesystem `mv` followed by `git add` — rejected because git may not detect the rename if files are modified simultaneously

### D2: Global sed replacement for command files

- **Decision**: Use `sed -i` for bulk path replacement across 9 command files
- **Rationale**: All 9 command files need the same `.specify/` → `.speckit/` replacement, making batch processing more reliable than individual edits
- **Alternatives considered**: Manual editing of each file — rejected as error-prone for repetitive changes

### D3: Reinforcement note in command files

- **Decision**: Add a blockquote note after frontmatter in each command file reminding that all SDD artifacts live under `.speckit/`
- **Rationale**: Prevents future drift if command files are edited without awareness of the consolidation
- **Alternatives considered**: No note — rejected because the path change is non-obvious to future contributors
