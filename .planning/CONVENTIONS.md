# Project Conventions

Rules that ALL plans and ALL agents MUST follow.

## NEVER PUSH WITHOUT TESTING

**ABSOLUTE RULE: Run `task before-push` before EVERY `git push`. NO EXCEPTIONS.**

```bash
task before-push    # MUST pass (exit code 0) before ANY push
task pr-qa-gate     # MUST pass before ANY PR creation/update
```

If it fails, fix it. Run again. Only push when clean.

## Plan Structure Requirements

Every execution plan MUST include these steps:

### Before Implementation
1. Ensure you are on a clean feature branch (not main)
2. `git status` — verify clean working tree or stash changes

### After Implementation
3. Run `task before-push` — verify exit code 0
4. Fix any failures (lint, type, test)
5. Run `task before-push` again after fixes
6. Only then: `git push`

### Before PR
7. Run `task pr-qa-gate` — verify exit code 0
8. Only then: create/update PR

## Code Quality Gates

| Gate | Command | Must Pass |
|------|---------|-----------|
| Format | `black` (line-length 88) | Yes |
| Lint | `ruff check` | Yes |
| Types | `mypy` (strict) | Yes |
| Tests | `pytest` (coverage >50%) | Yes |

## Common Failures to Watch

- **Line too long** (>88 chars): Run `black` to auto-fix
- **Missing type stubs**: Install with `pip install types-XXX`
- **Import order**: Run `ruff check --fix`
- **Type errors**: Fix manually, ensure all functions have type hints
