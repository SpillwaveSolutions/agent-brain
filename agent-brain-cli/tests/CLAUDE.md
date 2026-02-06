# Test Directory Guidelines for Claude Code

This directory contains tests for agent-brain-cli. Use the `/mastering-python-skill` skill for Python testing best practices.

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
- Testing Click CLI commands with `CliRunner`

### mocking-strategies.md
- Mocking HTTP client calls to the server
- Patching `httpx` or `requests` responses
- Using `MagicMock` for API client testing
- Testing error handling with mocked failures

### property-testing.md
- Testing CLI argument parsing with random inputs
- Verifying command behavior across input variations
- Using Hypothesis strategies for string inputs

## Test Commands

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=agent_brain_cli --cov-report=term-missing

# Run specific test file
poetry run pytest tests/test_commands.py -v

# Run with verbose output
poetry run pytest -v --tb=short
```

## CLI Testing Pattern

```python
from click.testing import CliRunner
from agent_brain_cli.cli import cli

def test_status_command():
    runner = CliRunner()
    result = runner.invoke(cli, ['status'])
    assert result.exit_code == 0
```

## Quality Standards

Before committing test changes:
- [ ] All tests pass (`poetry run pytest`)
- [ ] Coverage >= 50% for new code
- [ ] HTTP calls are properly mocked
- [ ] CLI commands tested with `CliRunner`
