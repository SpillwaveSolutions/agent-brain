# Test Directory Guidelines for AI Agents

This directory contains tests for agent-brain-server. For Claude Code users, the `/mastering-python-skill` skill provides pre-authorized tools and Python testing guidance.

## Skill Reference

**Claude Code users:** Invoke `/mastering-python-skill` for testing guidance with no approval fatigue.

## Testing References

When writing or modifying tests, use these references from the mastering-python-skill:

| Reference | Purpose |
|-----------|---------|
| `pytest-essentials.md` | Fixtures, parametrize, markers, conftest |
| `mocking-strategies.md` | unittest.mock, MagicMock, patching patterns |
| `property-testing.md` | Hypothesis property-based testing |

**Reference paths:** `.claude/skills/mastering-python-skill/references/testing/`

## Usage Guidelines

### For pytest (pytest-essentials.md)
- Use fixtures for setup/teardown
- Parametrize tests for multiple inputs
- Use markers for test categorization
- Follow naming: `test_<function>_<scenario>`

### For mocking (mocking-strategies.md)
- Mock external APIs (OpenAI, Anthropic)
- Use `@patch` decorator or context manager
- Prefer `AsyncMock` for async functions
- Clean up mocks after tests

### For property testing (property-testing.md)
- Use Hypothesis for input validation tests
- Define strategies for complex data types
- Combine with pytest fixtures

## Commands

```bash
poetry run pytest                                    # Run all tests
poetry run pytest --cov=agent_brain_server          # With coverage
poetry run pytest tests/unit/ -v                    # Unit tests only
```

## Quality Requirements

- All tests must pass before commit
- Minimum 50% coverage for new code
- Proper mock cleanup
- Use `pytest-asyncio` for async tests
