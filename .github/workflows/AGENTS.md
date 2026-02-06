# GitHub Workflows Guidelines for AI Agents

This directory contains CI/CD workflows for Agent Brain. For Claude Code users, the `/mastering-python-skill` skill provides CI/CD guidance.

## Skill Reference

**Claude Code users:** Invoke `/mastering-python-skill` for CI/CD guidance with no approval fatigue.

## Production References

When creating or modifying workflows, use these references:

| Reference | Purpose |
|-----------|---------|
| `ci-cd-pipelines.md` | GitHub Actions, workflow structure, matrix builds |
| `security.md` | Secret management, vulnerability scanning |
| `monitoring.md` | Coverage reporting, notifications |

**Reference paths:** `.claude/skills/mastering-python-skill/references/production/`

## Usage Guidelines

### For CI/CD (ci-cd-pipelines.md)
- Structure workflow jobs properly
- Use matrix builds for Python versions
- Cache Poetry/uv dependencies
- Set up PyPI publishing

### For security (security.md)
- Manage secrets properly
- Add dependency scanning
- Implement SAST checks

### For monitoring (monitoring.md)
- Add coverage reporting
- Set up failure notifications
- Track CI metrics

## Current Workflows

| File | Purpose |
|------|---------|
| `pr-qa-gate.yml` | PR quality gate (lint, type, test) |
| `publish-to-pypi.yml` | Publish to PyPI on release |

## Best Practices

- Use pinned action versions (`@v4` not `@latest`)
- Cache dependencies for faster builds
- Use matrix builds for compatibility testing
- Keep secrets in GitHub Secrets, not code

## Quality Requirements

- Test workflows locally with `act` when possible
- Never expose secrets in logs
- Include proper job dependencies
- Use meaningful job names
