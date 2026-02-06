# Integration Test Guidelines for Claude Code

This directory contains end-to-end integration tests for Agent Brain. Use the `/mastering-python-skill` skill for Python testing best practices.

## Required Skill

**Invoke:** `/mastering-python-skill`

This skill is bound to the `senior-python-engineer` agent with pre-authorized tools (no approval fatigue).

## Specific References for Testing

When writing or modifying integration tests, refer to these skill references:

| Reference | Use For | Path |
|-----------|---------|------|
| **pytest-essentials.md** | Fixtures, parametrize, markers, conftest patterns | `.claude/skills/mastering-python-skill/references/testing/pytest-essentials.md` |
| **mocking-strategies.md** | unittest.mock, pytest-mock, MagicMock, patching | `.claude/skills/mastering-python-skill/references/testing/mocking-strategies.md` |
| **property-testing.md** | Hypothesis, property-based testing, strategies | `.claude/skills/mastering-python-skill/references/testing/property-testing.md` |

## When to Use Each Reference

### pytest-essentials.md
- Creating session-scoped fixtures for server lifecycle
- Using `conftest.py` for shared test infrastructure
- Marking tests with `@pytest.mark.integration`
- Parametrizing tests for different query scenarios

### mocking-strategies.md
- Mocking external LLM APIs (OpenAI, Anthropic) in integration tests
- Stubbing responses for deterministic testing
- Using `respx` for async HTTP mocking

### property-testing.md
- Testing search functionality with generated queries
- Verifying index behavior with random documents
- Stress testing with Hypothesis

## Integration Test Commands

```bash
# Run integration tests
poetry run pytest e2e/integration/ -v

# Run with markers
poetry run pytest -m integration

# Run specific test
poetry run pytest e2e/integration/test_full_workflow.py -v

# Run with coverage
poetry run pytest e2e/integration/ --cov=agent_brain_server --cov=agent_brain_cli
```

## Fixture Pattern

```python
@pytest.fixture(scope="session")
async def running_server():
    """Start server for integration tests."""
    # Setup
    yield server_url
    # Teardown
```

## Quality Standards

Before committing integration test changes:
- [ ] All tests pass (`poetry run pytest e2e/integration/`)
- [ ] Tests clean up after themselves
- [ ] External APIs are mocked or use test keys
- [ ] Tests can run in CI environment
