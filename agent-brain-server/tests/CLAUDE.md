# Test Directory Guidelines for Claude Code

This directory contains tests for agent-brain-server. Use the `/mastering-python-skill` skill for Python testing best practices.

## Required Skill

**Invoke:** `/mastering-python-skill`

This skill is bound to the `senior-python-engineer` agent with pre-authorized tools (no approval fatigue).

## Specific References for Testing

When writing or modifying tests in this directory, refer to these skill references:

| Reference | Use For | Path |
|-----------|---------|------|
| **pytest-essentials.md** | Fixtures, parametrize, markers, conftest patterns | `.claude/skills/mastering-python-skill/references/testing/pytest-essentials.md` |
| **mocking-strategies.md** | unittest.mock, pytest-mock, MagicMock, patching | `.claude/skills/mastering-python-skill/references/testing/mocking-strategies.md` |
| **property-testing.md** | Hypothesis, property-based testing, strategies | `.claude/skills/mastering-python-skill/references/testing/property-testing.md` |

## When to Use Each Reference

### pytest-essentials.md
- Writing new test files
- Creating fixtures in `conftest.py`
- Using `@pytest.mark.parametrize` for test variations
- Test organization and naming conventions
- Using markers (`@pytest.mark.slow`, `@pytest.mark.integration`)

### mocking-strategies.md
- Mocking external services (OpenAI, Anthropic APIs)
- Patching ChromaDB or LlamaIndex components
- Using `MagicMock` and `AsyncMock`
- Testing async code with mocked dependencies

### property-testing.md
- Testing input validation with random data
- Verifying invariants across many inputs
- Using Hypothesis strategies
- Combining with pytest fixtures

## Test Commands

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=agent_brain_server --cov-report=term-missing

# Run specific test file
poetry run pytest tests/unit/test_query_service.py -v

# Run with markers
poetry run pytest -m "not slow"
```

## Quality Standards

Before committing test changes:
- [ ] All tests pass (`poetry run pytest`)
- [ ] Coverage >= 50% for new code
- [ ] Mocks are properly scoped and cleaned up
- [ ] Async tests use `pytest-asyncio`
