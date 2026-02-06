# Test Directory Guidelines for AI Agents

This directory contains tests for agent-brain-cli. For Claude Code users, the `/mastering-python-skill` skill provides pre-authorized tools and Python testing guidance.

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
- Use fixtures for CLI runner setup
- Parametrize tests for different command args
- Use `CliRunner` for Click command testing
- Follow naming: `test_<command>_<scenario>`

### For mocking (mocking-strategies.md)
- Mock HTTP client (httpx/requests)
- Patch server responses
- Use `responses` or `respx` libraries
- Test error handling with mocked failures

### For property testing (property-testing.md)
- Test argument parsing with random strings
- Verify URL validation with generated inputs
- Combine with Click's CliRunner

## CLI Testing Pattern

```python
from click.testing import CliRunner
from agent_brain_cli.cli import cli

def test_command():
    runner = CliRunner()
    result = runner.invoke(cli, ['command', '--arg', 'value'])
    assert result.exit_code == 0
```

## Commands

```bash
poetry run pytest                              # Run all tests
poetry run pytest --cov=agent_brain_cli       # With coverage
poetry run pytest tests/ -v                   # Verbose output
```

## Quality Requirements

- All tests must pass before commit
- Minimum 50% coverage for new code
- Mock all HTTP calls
- Use `CliRunner` for CLI tests
