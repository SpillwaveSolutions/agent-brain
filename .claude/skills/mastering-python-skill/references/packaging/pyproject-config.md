# pyproject.toml Configuration

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Minimal Configuration](#example-1-minimal-configuration)
  - [Example 2: Full Project Configuration](#example-2-full-project-configuration)
  - [Example 3: Tool Configuration](#example-3-tool-configuration)
  - [Example 4: Build System Configuration](#example-4-build-system-configuration)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Section | Purpose |
|---------|---------|
| `[build-system]` | Build tool requirements |
| `[project]` | Package metadata (PEP 621) |
| `[project.dependencies]` | Runtime dependencies |
| `[project.optional-dependencies]` | Extras/optional deps |
| `[project.scripts]` | CLI entry points |
| `[tool.*]` | Tool-specific config |

---

## Core Concepts

`pyproject.toml` is the standard Python project configuration file (PEP 518, 621):

- **Single Source of Truth**: Replaces setup.py, setup.cfg, requirements.txt
- **Declarative**: Describes what, not how (unlike executable setup.py)
- **Tool-Agnostic**: Works with pip, Poetry, Hatch, PDM, and more
- **Standardized Metadata**: PEP 621 defines project metadata format

**Key PEPs**:
| PEP | Purpose |
|-----|---------|
| 518 | Build system declaration (`[build-system]`) |
| 621 | Project metadata (`[project]`) |
| 517 | Build backend interface |
| 660 | Editable installs |

---

## Production Examples

### Example 1: Minimal Configuration

**Use case**: Simple package with basic metadata.

```toml
# Minimal pyproject.toml for a simple package

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-package"
version = "0.1.0"
description = "A simple Python package"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.28.0",
]
```

**Build and install**:

```bash
# Build distributions
python -m build

# Install in development mode
pip install -e .

# Install from source
pip install .
```

**Key points**:
- `[build-system]` is required for modern builds
- `requires-python` prevents installation on incompatible versions
- Dependencies use PEP 508 format (version specifiers, markers)

---

### Example 2: Full Project Configuration

**Use case**: Production-ready package with complete metadata.

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-awesome-package"
version = "1.0.0"
description = "A production-ready Python package"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
maintainers = [
    {name = "Maintainer Name", email = "maintainer@example.com"},
]
keywords = ["python", "api", "automation"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Typing :: Typed",
]

# Runtime dependencies
dependencies = [
    "httpx>=0.25.0",
    "pydantic>=2.0.0,<3.0.0",
    "click>=8.0.0",
]

# Optional dependencies (extras)
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.0.0",
]
all = [
    "my-awesome-package[dev,docs]",
]

# Project URLs
[project.urls]
Homepage = "https://github.com/yourorg/my-awesome-package"
Documentation = "https://my-awesome-package.readthedocs.io"
Repository = "https://github.com/yourorg/my-awesome-package.git"
Changelog = "https://github.com/yourorg/my-awesome-package/blob/main/CHANGELOG.md"
"Bug Tracker" = "https://github.com/yourorg/my-awesome-package/issues"

# CLI entry points
[project.scripts]
my-cli = "my_awesome_package.cli:main"
my-tool = "my_awesome_package.tools:run"

# GUI entry points (Windows)
[project.gui-scripts]
my-gui = "my_awesome_package.gui:main"

# Plugin entry points
[project.entry-points."my_awesome_package.plugins"]
default = "my_awesome_package.plugins.default:DefaultPlugin"
advanced = "my_awesome_package.plugins.advanced:AdvancedPlugin"
```

**Installing with extras**:

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Install with documentation dependencies
pip install -e ".[docs]"

# Install all extras
pip install -e ".[all]"

# Install specific extras for production
pip install "my-awesome-package[postgres,redis]"
```

**Key points**:
- Use classifiers for PyPI categorization and discoverability
- `[project.urls]` appears on PyPI package page
- Entry points enable CLI tools and plugin systems
- Optional dependencies allow flexible installation

---

### Example 3: Tool Configuration

**Use case**: Configure development tools in pyproject.toml.

```toml
# ============================================================
# TOOL CONFIGURATIONS
# ============================================================

# Black - Code formatter
[tool.black]
line-length = 88
target-version = ["py310", "py311", "py312"]
include = '\.pyi?$'
exclude = '''
/(
    \.git
    | \.hg
    | \.mypy_cache
    | \.tox
    | \.venv
    | _build
    | buck-out
    | build
    | dist
)/
'''

# Ruff - Fast linter (replaces flake8, isort, etc.)
[tool.ruff]
line-length = 88
target-version = "py310"
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # Pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "ARG",  # flake8-unused-arguments
    "SIM",  # flake8-simplify
]
ignore = [
    "E501",  # line too long (handled by black)
    "B008",  # function call in argument defaults
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports
"tests/*" = ["ARG001"]    # Allow unused arguments in tests

[tool.ruff.isort]
known-first-party = ["my_awesome_package"]
force-single-line = true

# MyPy - Type checker
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[[tool.mypy.overrides]]
module = [
    "httpx.*",
    "pytest.*",
]
ignore_missing_imports = true

# Pytest - Testing
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
pythonpath = ["src"]
addopts = [
    "-ra",
    "-q",
    "--strict-markers",
    "--strict-config",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning",
]
asyncio_mode = "auto"

# Coverage
[tool.coverage.run]
source = ["src"]
branch = true
parallel = true
omit = [
    "*/__init__.py",
    "*/tests/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
fail_under = 80
show_missing = true

[tool.coverage.paths]
source = [
    "src/",
    "*/site-packages/",
]

# Setuptools package discovery
[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"*" = ["py.typed", "*.pyi"]
```

**Running tools**:

```bash
# Format code
black src/ tests/
ruff format src/ tests/

# Lint code
ruff check src/ tests/
ruff check --fix src/ tests/  # Auto-fix

# Type check
mypy src/

# Run tests with coverage
pytest --cov=my_awesome_package --cov-report=html

# All checks (CI)
black --check src/ tests/
ruff check src/ tests/
mypy src/
pytest --cov=my_awesome_package --cov-fail-under=80
```

**Key points**:
- `[tool.*]` sections are tool-specific (not standardized)
- Ruff is modern and fast—can replace flake8, isort, pyupgrade
- Use strict mypy settings for new projects
- Configure pytest markers for test categorization

---

### Example 4: Build System Configuration

**Use case**: Configure different build backends.

**Setuptools** (traditional):

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
package-dir = {"" = "src"}
include-package-data = true

[tool.setuptools.packages.find]
where = ["src"]
include = ["my_package*"]
exclude = ["tests*"]

[tool.setuptools.package-data]
my_package = ["py.typed", "data/*.json"]

[tool.setuptools.dynamic]
version = {attr = "my_package.__version__"}
readme = {file = ["README.md"]}
```

**Hatchling** (modern, fast):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.version]
path = "src/my_package/__init__.py"

[tool.hatch.build.targets.sdist]
include = [
    "/src",
    "/tests",
]

[tool.hatch.build.targets.wheel]
packages = ["src/my_package"]
```

**Flit** (simple, pure Python):

```toml
[build-system]
requires = ["flit_core>=3.4"]
build-backend = "flit_core.buildapi"

[tool.flit.module]
name = "my_package"

[tool.flit.sdist]
include = ["doc/"]
exclude = ["doc/*.html"]
```

**Poetry-core** (Poetry ecosystem):

```toml
[build-system]
requires = ["poetry-core>=1.5.0"]
build-backend = "poetry.core.masonry.api"

# Poetry uses [tool.poetry] instead of [project]
[tool.poetry]
name = "my-package"
version = "1.0.0"
description = "My package"
authors = ["Your Name <you@example.com>"]
packages = [{include = "my_package", from = "src"}]
```

**Maturin** (Rust extensions):

```toml
[build-system]
requires = ["maturin>=1.0"]
build-backend = "maturin"

[tool.maturin]
features = ["pyo3/extension-module"]
python-source = "python"
module-name = "my_rust_package._core"
```

**Build and verify**:

```bash
# Build with any backend
python -m build

# Check distribution
twine check dist/*

# Inspect wheel contents
unzip -l dist/*.whl

# Install and test
pip install dist/*.whl
python -c "import my_package; print(my_package.__version__)"
```

**Key points**:
- Choose build backend based on needs (setuptools for C extensions, hatch for speed)
- Setuptools is most compatible, Hatch/Flit are simpler for pure Python
- Poetry-core only for Poetry-managed projects
- Maturin for Rust-based Python extensions

---

## Common Patterns

### Pattern: Dynamic Version from Git
```toml
[build-system]
requires = ["setuptools>=61.0", "setuptools-scm>=8.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools_scm]
write_to = "src/my_package/_version.py"
version_scheme = "python-simplified-semver"
```

### Pattern: Conditional Dependencies
```toml
[project]
dependencies = [
    "tomli>=2.0; python_version < '3.11'",
    "typing-extensions>=4.0; python_version < '3.10'",
]
```

### Pattern: Platform-Specific Dependencies
```toml
[project]
dependencies = [
    "pywin32>=306; sys_platform == 'win32'",
    "uvloop>=0.19; sys_platform != 'win32'",
]
```

### Pattern: Namespace Packages
```toml
[tool.setuptools.packages.find]
where = ["src"]
namespaces = true
```

---

## Pitfalls to Avoid

**Don't do this:**
```toml
# Missing build-system section
[project]
name = "my-package"
# pip will use legacy setup.py behavior!
```

**Do this instead:**
```toml
# Always include build-system
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "my-package"
```

---

**Don't do this:**
```toml
# Mixing Poetry's [tool.poetry] with [project]
[project]
name = "my-package"

[tool.poetry.dependencies]
python = "^3.11"
# Confusing! Which one is used?
```

**Do this instead:**
```toml
# Use one or the other consistently
# For Poetry:
[tool.poetry]
name = "my-package"
# OR for standard PEP 621:
[project]
name = "my-package"
```

---

**Don't do this:**
```toml
# Overly broad version constraints
[project]
dependencies = [
    "requests",  # Any version!
]
```

**Do this instead:**
```toml
# Specify minimum versions
[project]
dependencies = [
    "requests>=2.28.0",
    "pydantic>=2.0.0,<3.0.0",
]
```

---

## See Also

- [poetry-workflow.md](poetry-workflow.md) - Poetry dependency management
- [project-structure.md](../foundations/project-structure.md) - Project layout
- [code-quality.md](../foundations/code-quality.md) - Linting and formatting
