# Implementation Plan: Deprecation Warning Fixes

## Overview

This plan addresses three deprecation warnings to ensure forward compatibility with Pydantic V3 and future pytest-asyncio versions.

## Research Summary

### Pydantic V2 Settings (via Perplexity)
- `class Config:` is deprecated since Pydantic V2.0
- Use `model_config = SettingsConfigDict(...)` instead
- Import `SettingsConfigDict` from `pydantic_settings`
- All config options remain compatible

### pytest-asyncio 0.24+ (via Perplexity)
- Custom `event_loop` fixtures are deprecated
- Use `asyncio_default_fixture_loop_scope` config option
- Use `@pytest.mark.asyncio(scope="...")` for specific scopes
- Plugin creates loops automatically now

### validate_default Warning (via Perplexity)
- Warning from Pydantic internals, not explicit usage
- Occurs in dependencies (chromadb, llama-index)
- Cannot fix in our code, must filter

## Implementation Phases

### Phase 1: Fix Settings (settings.py)

**Before:**
```python
class Settings(BaseSettings):
    ...
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
```

**After:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ...
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
```

### Phase 2: Fix Event Loop (conftest.py)

Remove the following fixture entirely:
```python
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

### Phase 3: Update pytest Config (pyproject.toml)

Add configuration for pytest-asyncio loop scope and warning filters:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
filterwarnings = [
    "ignore::pydantic._internal._generate_schema.UnsupportedFieldAttributeWarning",
]
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Settings don't load | High | Test settings import immediately |
| Async tests fail | High | Run full test suite after changes |
| New warnings appear | Low | Review all test output |

## Verification

```bash
# Run tests and check for warnings
task test 2>&1 | grep -E "(warning|Warning|WARN)"

# Expected output: empty (no warnings)
```
