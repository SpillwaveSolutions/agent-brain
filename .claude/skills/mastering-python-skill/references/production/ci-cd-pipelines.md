# CI/CD Pipelines

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Basic GitHub Actions Workflow](#example-1-basic-github-actions-workflow)
  - [Example 2: Comprehensive CI Pipeline](#example-2-comprehensive-ci-pipeline)
  - [Example 3: CD Pipeline with Staging](#example-3-cd-pipeline-with-staging)
  - [Example 4: Matrix Testing](#example-4-matrix-testing)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code/Config |
|------|-------------|
| Trigger on push | `on: [push, pull_request]` |
| Python setup | `uses: actions/setup-python@v5` |
| Cache pip | `uses: actions/cache@v4` with `~/.cache/pip` |
| Run tests | `run: pytest --cov=src --cov-report=xml` |
| Upload coverage | `uses: codecov/codecov-action@v4` |
| Security scan | `run: bandit -r src/ -f json` |
| Dependency check | `run: pip-audit --strict` |

---

## Core Concepts

CI/CD (Continuous Integration/Continuous Deployment) automates the build, test, and deployment pipeline:

- **Continuous Integration**: Automatically build and test on every commit
- **Continuous Deployment**: Automatically deploy passing builds to environments
- **Pipeline Stages**: lint → test → build → deploy (fail fast)
- **Environment Progression**: dev → staging → production

**Key Principles**:
| Principle | Description |
|-----------|-------------|
| Fail Fast | Run quick checks (lint) before slow ones (integration tests) |
| Reproducibility | Pin versions, use lock files, deterministic builds |
| Isolation | Each job runs in clean environment |
| Caching | Cache dependencies to speed up pipelines |

---

## Production Examples

### Example 1: Basic GitHub Actions Workflow

**Use case**: Simple CI for Python projects with linting and testing.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Lint with ruff
        run: ruff check src/ tests/

      - name: Type check with mypy
        run: mypy src/

      - name: Run tests
        run: pytest tests/ -v --tb=short
```

**Key points**:
- `actions/checkout@v4` fetches code with git history
- Cache key uses hash of requirements files for invalidation
- Lint and type check run before slower tests

---

### Example 2: Comprehensive CI Pipeline

**Use case**: Full CI with coverage, security scanning, and artifact publishing.

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:

env:
  PYTHON_VERSION: "3.12"
  POETRY_VERSION: "1.7.1"

jobs:
  # ============================================================
  # QUALITY CHECKS (Fast - run first)
  # ============================================================
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install linters
        run: pip install ruff black

      - name: Check formatting
        run: black --check src/ tests/

      - name: Lint code
        run: ruff check src/ tests/

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: ${{ env.POETRY_VERSION }}

      - name: Install dependencies
        run: poetry install --only main,dev

      - name: Run mypy
        run: poetry run mypy src/

  # ============================================================
  # SECURITY CHECKS
  # ============================================================
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install security tools
        run: pip install bandit pip-audit safety

      - name: Run bandit (SAST)
        run: bandit -r src/ -f json -o bandit-report.json || true

      - name: Check dependencies for vulnerabilities
        run: pip-audit --strict

      - name: Upload security report
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: bandit-report.json

  # ============================================================
  # TESTS
  # ============================================================
  test:
    runs-on: ubuntu-latest
    needs: [lint]  # Only run if lint passes

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: ${{ env.POETRY_VERSION }}
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Load cached venv
        id: cached-poetry-deps
        uses: actions/cache@v4
        with:
          path: .venv
          key: venv-${{ runner.os }}-${{ env.PYTHON_VERSION }}-${{ hashFiles('**/poetry.lock') }}

      - name: Install dependencies
        if: steps.cached-poetry-deps.outputs.cache-hit != 'true'
        run: poetry install --no-interaction

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb
        run: |
          poetry run pytest tests/ \
            --cov=src \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=80 \
            -v

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          fail_ci_if_error: true

      - name: Upload coverage HTML report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/

  # ============================================================
  # BUILD
  # ============================================================
  build:
    runs-on: ubuntu-latest
    needs: [test, type-check, security]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1

      - name: Build package
        run: poetry build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

**Key points**:
- Jobs run in parallel where possible (`lint`, `type-check`, `security`)
- `needs` creates dependencies between jobs
- Services (Postgres) available for integration tests
- Artifacts persist between jobs and for download

---

### Example 3: CD Pipeline with Staging

**Use case**: Deploy to staging on develop, production on main with approval.

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main, develop]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        type: choice
        options:
          - staging
          - production

jobs:
  # ============================================================
  # BUILD DOCKER IMAGE
  # ============================================================
  build:
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ============================================================
  # DEPLOY TO STAGING
  # ============================================================
  deploy-staging:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/develop' || github.event.inputs.environment == 'staging'
    environment:
      name: staging
      url: https://staging.example.com

    steps:
      - name: Deploy to staging
        run: |
          echo "Deploying ${{ needs.build.outputs.image_tag }} to staging"
          # kubectl set image deployment/app app=${{ needs.build.outputs.image_tag }}
          # Or use your deployment tool of choice

      - name: Run smoke tests
        run: |
          echo "Running smoke tests against staging..."
          # curl -f https://staging.example.com/health

      - name: Notify on success
        if: success()
        run: |
          echo "Staging deployment successful!"

  # ============================================================
  # DEPLOY TO PRODUCTION
  # ============================================================
  deploy-production:
    runs-on: ubuntu-latest
    needs: [build, deploy-staging]
    if: github.ref == 'refs/heads/main' || github.event.inputs.environment == 'production'
    environment:
      name: production
      url: https://example.com

    steps:
      - name: Deploy to production
        run: |
          echo "Deploying ${{ needs.build.outputs.image_tag }} to production"

      - name: Run production smoke tests
        run: |
          echo "Running production smoke tests..."

      - name: Create release tag
        if: github.ref == 'refs/heads/main'
        uses: actions/github-script@v7
        with:
          script: |
            const date = new Date().toISOString().split('T')[0];
            const sha = context.sha.substring(0, 7);
            const tag = `release-${date}-${sha}`;

            await github.rest.git.createRef({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: `refs/tags/${tag}`,
              sha: context.sha
            });
```

**Key points**:
- `environment` enables GitHub environment protection rules
- Production requires manual approval (configured in repo settings)
- `workflow_dispatch` allows manual deployments
- Docker layer caching via GitHub Actions cache

---

### Example 4: Matrix Testing

**Use case**: Test across multiple Python versions and operating systems.

```yaml
# .github/workflows/matrix.yml
name: Matrix Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.10", "3.11", "3.12"]
        exclude:
          # Exclude slow combinations
          - os: macos-latest
            python-version: "3.10"
        include:
          # Add specific configuration
          - os: ubuntu-latest
            python-version: "3.12"
            coverage: true

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest tests/ -v ${{ matrix.coverage && '--cov=src --cov-report=xml' || '' }}

      - name: Upload coverage
        if: matrix.coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  # Aggregate results for branch protection
  all-tests-pass:
    runs-on: ubuntu-latest
    needs: test
    if: always()
    steps:
      - name: Check matrix results
        run: |
          if [ "${{ needs.test.result }}" != "success" ]; then
            echo "Matrix tests failed"
            exit 1
          fi
          echo "All matrix tests passed!"
```

**Key points**:
- `fail-fast: false` continues other jobs if one fails
- `exclude` removes specific combinations
- `include` adds extra configuration to specific combinations
- Aggregate job for branch protection rules

---

## Common Patterns

### Pattern: Reusable Workflow
```yaml
# .github/workflows/reusable-test.yml
name: Reusable Test Workflow

on:
  workflow_call:
    inputs:
      python-version:
        required: true
        type: string

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
      - run: pytest

# Usage in another workflow:
# jobs:
#   call-tests:
#     uses: ./.github/workflows/reusable-test.yml
#     with:
#       python-version: "3.12"
```

### Pattern: Conditional Job Execution
```yaml
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.filter.outputs.backend }}
    steps:
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            backend:
              - 'src/**'
              - 'tests/**'

  test:
    needs: changes
    if: needs.changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: pytest
```

### Pattern: Secret Scanning Prevention
```yaml
jobs:
  secrets-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Detect secrets
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          extra_args: --only-verified
```

---

## Pitfalls to Avoid

**Don't do this:**
```yaml
# Hardcoding secrets in workflow files
env:
  API_KEY: "sk-1234567890abcdef"  # NEVER DO THIS!
```

**Do this instead:**
```yaml
# Use GitHub secrets
env:
  API_KEY: ${{ secrets.API_KEY }}
```

---

**Don't do this:**
```yaml
# Not pinning action versions
- uses: actions/checkout@main  # Dangerous - could change!
```

**Do this instead:**
```yaml
# Pin to specific version or SHA
- uses: actions/checkout@v4  # Or full SHA for maximum security
```

---

**Don't do this:**
```yaml
# Running everything sequentially
jobs:
  job1:
    steps: [lint, test, build, deploy]  # All sequential!
```

**Do this instead:**
```yaml
# Parallel jobs with dependencies
jobs:
  lint:
    ...
  test:
    needs: lint  # Only depends on lint
  build:
    needs: [lint, test]  # Waits for both
```

---

## See Also

- [docker-deployment.md](../packaging/docker-deployment.md) - Container builds
- [security.md](security.md) - Security scanning details
- [monitoring.md](monitoring.md) - Post-deployment observability
