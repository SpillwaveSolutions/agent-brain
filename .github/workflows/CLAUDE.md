# GitHub Workflows Guidelines for Claude Code

This directory contains CI/CD workflows for Agent Brain. Use the `/mastering-python-skill` skill for Python CI/CD best practices.

## Required Skill

**Invoke:** `/mastering-python-skill`

This skill is bound to the `senior-python-engineer` agent with pre-authorized tools (no approval fatigue).

## Specific References for CI/CD

When creating or modifying GitHub Actions workflows, refer to these skill references:

| Reference | Use For | Path |
|-----------|---------|------|
| **ci-cd-pipelines.md** | GitHub Actions, workflow structure, matrix builds | `.claude/skills/mastering-python-skill/references/production/ci-cd-pipelines.md` |
| **security.md** | Secret management, dependency scanning, SAST | `.claude/skills/mastering-python-skill/references/production/security.md` |
| **monitoring.md** | Logging, metrics, observability in CI | `.claude/skills/mastering-python-skill/references/production/monitoring.md` |

## When to Use Each Reference

### ci-cd-pipelines.md
- Creating new workflow files
- Setting up matrix builds for Python versions
- Configuring test and lint jobs
- Publishing to PyPI
- Caching dependencies with Poetry/uv

### security.md
- Managing secrets (API keys, tokens)
- Adding dependency vulnerability scanning
- Implementing security checks in CI
- OWASP dependency-check integration

### monitoring.md
- Adding test coverage reporting
- Integrating with coverage services
- Setting up failure notifications
- Performance monitoring in CI

## Current Workflows

| Workflow | Purpose |
|----------|---------|
| `pr-qa-gate.yml` | Quality gate for pull requests (lint, type, test) |
| `publish-to-pypi.yml` | Publish packages to PyPI on release |

## Workflow Best Practices

```yaml
# Cache Poetry dependencies
- name: Cache Poetry
  uses: actions/cache@v4
  with:
    path: ~/.cache/pypoetry
    key: ${{ runner.os }}-poetry-${{ hashFiles('**/poetry.lock') }}

# Matrix for Python versions
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']
```

## Quality Standards

Before modifying workflows:
- [ ] Test workflow locally with `act` if possible
- [ ] Ensure secrets are not exposed
- [ ] Use pinned action versions
- [ ] Include proper job dependencies
