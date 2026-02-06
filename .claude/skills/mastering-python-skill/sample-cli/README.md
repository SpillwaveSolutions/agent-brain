# Sample CLI Tools

Runnable examples demonstrating Python patterns from the reference documentation.

## Prerequisites

Install dependencies:

```bash
pip install httpx pydantic pydantic-settings sqlalchemy aiosqlite python-dotenv ruff mypy
```

Or with Poetry:

```bash
poetry add httpx pydantic pydantic-settings sqlalchemy aiosqlite python-dotenv
poetry add --group dev ruff mypy
```

## Tools

### 1. Async Fetcher (`async_fetcher.py`)

Demonstrates async HTTP client patterns from [async-programming.md](../references/patterns/async-programming.md).

**Features:**
- Async/await with httpx
- Concurrent requests with asyncio.gather()
- Rate limiting and timeout handling
- Structured error handling

**Usage:**

```bash
# Fetch single URL
python sample-cli/async_fetcher.py https://api.github.com

# Fetch multiple URLs concurrently
python sample-cli/async_fetcher.py https://httpbin.org/get https://api.github.com

# With rate limit (max concurrent requests)
python sample-cli/async_fetcher.py --concurrency 3 url1 url2 url3 url4 url5
```

---

### 2. Config Loader (`config_loader.py`)

Demonstrates Pydantic settings patterns from [pydantic-validation.md](../references/web-apis/pydantic-validation.md).

**Features:**
- Environment variable loading
- .env file support
- Type validation and coercion
- Nested configuration models
- Secret handling with SecretStr

**Usage:**

```bash
# Show default configuration
python sample-cli/config_loader.py

# With environment variables
APP_DEBUG=true APP_LOG_LEVEL=DEBUG python sample-cli/config_loader.py

# With .env file (create .env in current directory)
echo "APP_DEBUG=true" > .env
echo "DATABASE_URL=postgresql://localhost/mydb" >> .env
python sample-cli/config_loader.py
```

---

### 3. Database CLI (`db_cli.py`)

Demonstrates SQLAlchemy async patterns from [database-access.md](../references/web-apis/database-access.md).

**Features:**
- Async SQLAlchemy with aiosqlite
- Repository pattern
- CRUD operations
- Transaction management

**Usage:**

```bash
# Initialize database and add sample data
python sample-cli/db_cli.py init

# List all users
python sample-cli/db_cli.py list

# Add a user
python sample-cli/db_cli.py add "John Doe" john@example.com

# Get user by ID
python sample-cli/db_cli.py get 1

# Update user
python sample-cli/db_cli.py update 1 --name "Jane Doe" --email jane@example.com

# Delete user
python sample-cli/db_cli.py delete 1
```

---

### 4. Code Validator (`code_validator.py`)

Demonstrates run→check→fix validation patterns from [code-quality.md](../references/foundations/code-quality.md).

**Features:**
- Ruff linting with auto-fix
- Ruff format checking
- Mypy type checking (optional strict mode)
- Aggregated validation report
- Clear pass/fail summary

**Usage:**

```bash
# Check only (no changes)
python sample-cli/code_validator.py src/

# Auto-fix lint and format issues
python sample-cli/code_validator.py src/ --fix

# Strict mypy mode
python sample-cli/code_validator.py src/ --strict

# Fix and strict check
python sample-cli/code_validator.py . --fix --strict
```

**Example output:**

```
Checking src/...

============================================================
VALIDATION SUMMARY
============================================================
[✓ PASS] Ruff Lint
[✓ PASS] Ruff Format
[✓ PASS] Mypy Types
------------------------------------------------------------
✓ All checks passed!
============================================================
```

---

## Running Tests

Each CLI tool includes basic validation. Run them to verify your environment:

```bash
# Quick smoke tests
python sample-cli/async_fetcher.py https://httpbin.org/get
python sample-cli/config_loader.py
python sample-cli/db_cli.py init && python sample-cli/db_cli.py list
python sample-cli/code_validator.py sample-cli/
```

## Related Documentation

| Tool | Reference |
|------|-----------|
| async_fetcher.py | [async-programming.md](../references/patterns/async-programming.md) |
| config_loader.py | [pydantic-validation.md](../references/web-apis/pydantic-validation.md) |
| db_cli.py | [database-access.md](../references/web-apis/database-access.md) |
| code_validator.py | [code-quality.md](../references/foundations/code-quality.md) |
