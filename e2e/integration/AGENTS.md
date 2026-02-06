# Integration Test Guidelines for AI Agents

This directory contains end-to-end integration tests for Agent Brain. For Claude Code users, the `/mastering-python-skill` skill provides pre-authorized tools and testing guidance.

## Skill Reference

**Claude Code users:** Invoke `/mastering-python-skill` for testing guidance with no approval fatigue.

## Testing References

When writing or modifying integration tests, use these references:

| Reference | Purpose |
|-----------|---------|
| `pytest-essentials.md` | Fixtures, parametrize, markers, conftest |
| `mocking-strategies.md` | unittest.mock, MagicMock, patching patterns |
| `property-testing.md` | Hypothesis property-based testing |

**Reference paths:** `.claude/skills/mastering-python-skill/references/testing/`

## Usage Guidelines

### For pytest (pytest-essentials.md)
- Use session-scoped fixtures for server lifecycle
- Create shared fixtures in `conftest.py`
- Mark tests: `@pytest.mark.integration`
- Parametrize for multiple scenarios

### For mocking (mocking-strategies.md)
- Mock LLM APIs for deterministic tests
- Use `respx` for async HTTP mocking
- Stub external service responses

### For property testing (property-testing.md)
- Generate random search queries
- Test index with generated documents
- Stress test with Hypothesis

## Commands

```bash
poetry run pytest e2e/integration/ -v          # Run integration tests
poetry run pytest -m integration               # Run by marker
poetry run pytest e2e/integration/ --cov      # With coverage
```

## Quality Requirements

- All tests must pass before commit
- Tests must clean up resources
- External APIs mocked or use test credentials
- Tests must run in CI environment
