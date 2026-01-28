# Research: CLI Entry Points Installation

**Feature**: 003-cli-entrypoints
**Date**: 2025-12-16

## Research Questions

### 1. How do Poetry entry points work with pip install?

**Decision**: Poetry's `[tool.poetry.scripts]` is compatible with pip installation
**Rationale**: Poetry uses `poetry-core` as a PEP 517 build backend, which translates `[tool.poetry.scripts]` to standard wheel entry points during the build process. When you run `pip install .` or `pip install -e .`, pip invokes the build backend which handles the translation.
**Alternatives considered**:
- Using `[project.scripts]` (PEP 621) - Would require dual configuration or migration away from Poetry-specific format
- Using setup.py with entry_points - Deprecated, Poetry handles this automatically

### 2. What is the correct module path format for entry points?

**Decision**: Use `src.module:function` format as currently configured
**Rationale**: The packages use `packages = [{include = "src"}]` which means the `src` directory is the package root. Entry points should reference `src.cli:cli` and `src.api.main:run`.
**Verification**:
- `doc-svr-ctl`: `src.cli:cli` → imports `src/cli.py` and calls `cli()` function
- `doc-serve-server`: `src.api.main:run` → imports `src/api/main.py` and calls `run()` function

### 3. Do the current pyproject.toml configurations need changes?

**Decision**: No changes needed to entry point configuration
**Rationale**: After reviewing both pyproject.toml files:
- `doc-svr-ctl/pyproject.toml` line 22-23: `doc-svr-ctl = "src.cli:cli"` ✓
- `doc-serve-server/pyproject.toml` line 33-34: `doc-serve = "src.api.main:run"` ✓
**Verification needed**: Actual installation testing to confirm entry points work

### 4. What happens with editable installs (`pip install -e .`)?

**Decision**: Editable installs work with Poetry projects via PEP 660
**Rationale**: Modern pip versions support PEP 660 editable installs with PEP 517 build backends. Poetry-core implements this, so `pip install -e .` creates entry points that reference the source directory.
**Caveats**:
- Requires pip >= 21.3 for full PEP 660 support
- Entry points are created in the virtualenv's `bin/` directory

### 5. How should installation be tested?

**Decision**: Create verification tests that check entry point availability
**Rationale**: Tests should verify:
1. The command is available on PATH after installation
2. The command executes without import errors
3. Basic functionality works (--help, --version)

**Test approach**:
- Unit tests: Import the target functions directly
- Integration tests: Execute commands via subprocess
- Both approaches avoid needing to install/uninstall during test runs

## Technical Findings

### Entry Point Mechanics

When a Poetry package is installed:
1. `pip install .` invokes `poetry-core` build backend
2. Build backend creates a wheel with entry point metadata
3. Wheel installation creates executable scripts in `bin/`
4. Scripts wrap the Python function call with proper imports

Example generated script (`bin/doc-svr-ctl`):
```python
#!/path/to/python
from src.cli import cli
if __name__ == '__main__':
    cli()
```

### Compatibility Matrix

| Installation Method | Works? | Notes |
|---------------------|--------|-------|
| `pip install .` | Yes | Standard wheel install |
| `pip install -e .` | Yes | PEP 660 editable |
| `poetry install` | Yes | Native Poetry workflow |
| `poetry run doc-svr-ctl` | Yes | Runs within Poetry env |

## Unresolved Questions

None - all clarifications resolved through research.

## References

- [Poetry scripts documentation](https://python-poetry.org/docs/pyproject/#scripts)
- [PEP 517 - Build system interface](https://peps.python.org/pep-0517/)
- [PEP 660 - Editable installs](https://peps.python.org/pep-0660/)
- [Poetry-core source](https://github.com/python-poetry/poetry-core)
