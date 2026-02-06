# Pytest Essentials

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Fixtures with Scopes](#example-1-fixtures-with-scopes)
  - [Example 2: Parametrized Testing](#example-2-parametrized-testing)
  - [Example 3: Markers and Test Selection](#example-3-markers-and-test-selection)
  - [Example 4: Async Testing with pytest-asyncio](#example-4-async-testing-with-pytest-asyncio)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Run all tests | `pytest` |
| Run with verbose | `pytest -v` |
| Run specific file | `pytest test_module.py` |
| Run specific test | `pytest test_module.py::test_function` |
| Run by marker | `pytest -m slow` |
| Run by keyword | `pytest -k "login"` |
| Show print output | `pytest -s` |
| Stop on first fail | `pytest -x` |
| Run last failed | `pytest --lf` |
| Parallel execution | `pytest -n auto` (requires pytest-xdist) |
| Coverage report | `pytest --cov=src --cov-report=html` |

---

## Core Concepts

Pytest is Python's most powerful testing framework, offering:

- **Auto-discovery**: Finds tests in `test_*.py` files and `test_*` functions
- **Fixtures**: Reusable setup/teardown with dependency injection
- **Parametrization**: Run same test with different inputs
- **Markers**: Categorize and selectively run tests
- **Plugins**: Extensible ecosystem (pytest-cov, pytest-asyncio, pytest-xdist)

The testing pyramid guides test distribution: many unit tests (fast, isolated), fewer integration tests (verify components work together), minimal E2E tests (slow but validate full system).

---

## Production Examples

### Example 1: Fixtures with Scopes

**Use case**: Set up expensive resources once and share across tests.

```python
#!/usr/bin/env python3
"""Pytest fixtures with different scopes."""

import pytest
from dataclasses import dataclass
from typing import Generator


@dataclass
class DatabaseConnection:
    """Simulated database connection."""

    host: str
    connected: bool = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def execute(self, query: str) -> list[dict]:
        if not self.connected:
            raise RuntimeError("Not connected")
        return [{"result": query}]


@dataclass
class User:
    """Test user model."""

    id: int
    name: str
    email: str


# Module-scoped fixture: created once per test module
@pytest.fixture(scope="module")
def db_connection() -> Generator[DatabaseConnection, None, None]:
    """Database connection shared across all tests in module."""
    conn = DatabaseConnection(host="localhost")
    conn.connect()
    print("\n[Setup] Database connected")
    yield conn
    conn.disconnect()
    print("\n[Teardown] Database disconnected")


# Function-scoped fixture (default): created for each test
@pytest.fixture
def sample_user() -> User:
    """Fresh user for each test."""
    return User(id=1, name="Test User", email="test@example.com")


# Fixture with factory pattern
@pytest.fixture
def user_factory():
    """Factory fixture for creating multiple users."""
    created_users: list[User] = []

    def _create_user(name: str, email: str) -> User:
        user = User(id=len(created_users) + 1, name=name, email=email)
        created_users.append(user)
        return user

    yield _create_user

    # Cleanup after test
    print(f"\n[Teardown] Cleaning up {len(created_users)} users")


# Fixture using another fixture
@pytest.fixture
def authenticated_user(sample_user: User, db_connection: DatabaseConnection) -> User:
    """User that has been 'authenticated' against the database."""
    db_connection.execute(f"SELECT * FROM users WHERE id = {sample_user.id}")
    return sample_user


class TestUserOperations:
    """Tests demonstrating fixture usage."""

    def test_user_creation(self, sample_user: User) -> None:
        """Each test gets a fresh sample_user."""
        assert sample_user.id == 1
        assert sample_user.name == "Test User"

    def test_database_query(self, db_connection: DatabaseConnection) -> None:
        """All tests in module share the same db_connection."""
        result = db_connection.execute("SELECT 1")
        assert result == [{"result": "SELECT 1"}]

    def test_factory_creates_multiple(self, user_factory) -> None:
        """Factory fixture allows creating multiple instances."""
        user1 = user_factory("Alice", "alice@example.com")
        user2 = user_factory("Bob", "bob@example.com")
        assert user1.id == 1
        assert user2.id == 2

    def test_authenticated_user(self, authenticated_user: User) -> None:
        """Fixture can depend on other fixtures."""
        assert authenticated_user.name == "Test User"
```

**Key points**:
- `scope="module"` creates fixture once per file, `scope="session"` once per test run
- Use `yield` for setup/teardown pattern
- Factory fixtures create multiple instances within a single test

---

### Example 2: Parametrized Testing

**Use case**: Run the same test logic with different inputs and expected outputs.

```python
#!/usr/bin/env python3
"""Parametrized testing patterns."""

import pytest
from typing import Any


def is_palindrome(s: str) -> bool:
    """Check if string is a palindrome."""
    cleaned = "".join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]


def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate discounted price."""
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")
    return round(price * (1 - discount_percent / 100), 2)


class Calculator:
    """Simple calculator for demonstration."""

    def add(self, a: float, b: float) -> float:
        return a + b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return a / b


# Basic parametrization
@pytest.mark.parametrize(
    "input_string,expected",
    [
        ("radar", True),
        ("hello", False),
        ("A man a plan a canal Panama", True),
        ("", True),
        ("a", True),
        ("Race Car", True),  # Case insensitive
    ],
)
def test_is_palindrome(input_string: str, expected: bool) -> None:
    """Test palindrome checker with multiple inputs."""
    assert is_palindrome(input_string) == expected


# Parametrize with IDs for better test names
@pytest.mark.parametrize(
    "price,discount,expected",
    [
        pytest.param(100.0, 10, 90.0, id="10% off"),
        pytest.param(100.0, 0, 100.0, id="no discount"),
        pytest.param(100.0, 100, 0.0, id="free"),
        pytest.param(49.99, 25, 37.49, id="25% off odd price"),
    ],
)
def test_calculate_discount(price: float, discount: float, expected: float) -> None:
    """Test discount calculation with named test cases."""
    assert calculate_discount(price, discount) == expected


# Parametrize exceptions
@pytest.mark.parametrize(
    "price,discount",
    [
        (100.0, -10),
        (100.0, 150),
    ],
)
def test_calculate_discount_invalid(price: float, discount: float) -> None:
    """Test that invalid discounts raise ValueError."""
    with pytest.raises(ValueError, match="must be between 0 and 100"):
        calculate_discount(price, discount)


# Multiple parametrize decorators (cartesian product)
@pytest.mark.parametrize("a", [1, 2, 3])
@pytest.mark.parametrize("b", [10, 20])
def test_add_combinations(a: int, b: int) -> None:
    """Tests all combinations: (1,10), (1,20), (2,10), (2,20), (3,10), (3,20)."""
    calc = Calculator()
    result = calc.add(a, b)
    assert result == a + b


# Parametrize at class level
@pytest.mark.parametrize("value", [1, 2, 3])
class TestCalculatorWithValue:
    """All methods receive the parametrized value."""

    def test_add_to_self(self, value: int) -> None:
        calc = Calculator()
        assert calc.add(value, value) == value * 2

    def test_divide_by_one(self, value: int) -> None:
        calc = Calculator()
        assert calc.divide(value, 1) == value


# Indirect parametrization with fixtures
@pytest.fixture
def user_by_role(request) -> dict[str, Any]:
    """Create user based on parametrized role."""
    roles = {
        "admin": {"name": "Admin User", "permissions": ["read", "write", "delete"]},
        "editor": {"name": "Editor User", "permissions": ["read", "write"]},
        "viewer": {"name": "Viewer User", "permissions": ["read"]},
    }
    return roles[request.param]


@pytest.mark.parametrize("user_by_role", ["admin", "editor", "viewer"], indirect=True)
def test_user_has_read_permission(user_by_role: dict[str, Any]) -> None:
    """All users should have read permission."""
    assert "read" in user_by_role["permissions"]
```

**Key points**:
- Use `pytest.param(..., id="name")` for readable test names
- Multiple `@parametrize` decorators create cartesian product
- `indirect=True` passes parameter to a fixture instead of the test

---

### Example 3: Markers and Test Selection

**Use case**: Categorize tests and run subsets based on markers.

```python
#!/usr/bin/env python3
"""Pytest markers for test categorization."""

import pytest
import time
from typing import Generator


# Register custom markers in conftest.py or pyproject.toml
# [tool.pytest.ini_options]
# markers = [
#     "slow: marks tests as slow",
#     "integration: marks tests as integration tests",
#     "smoke: critical tests for deployment verification",
# ]


@pytest.mark.slow
def test_large_data_processing() -> None:
    """Test that processes large dataset - marked as slow."""
    time.sleep(0.1)  # Simulate slow operation
    data = list(range(10000))
    assert sum(data) == 49995000


@pytest.mark.integration
def test_database_connection() -> None:
    """Integration test requiring database."""
    # Would connect to real database
    assert True


@pytest.mark.smoke
def test_api_health_check() -> None:
    """Critical smoke test for deployment."""
    # Would check API health
    assert True


@pytest.mark.smoke
@pytest.mark.integration
def test_critical_integration() -> None:
    """Test with multiple markers."""
    assert True


# Skip markers
@pytest.mark.skip(reason="Feature not implemented yet")
def test_future_feature() -> None:
    """This test is always skipped."""
    assert False


@pytest.mark.skipif(
    condition=True,  # Would be: sys.platform == "win32"
    reason="Not supported on Windows",
)
def test_unix_only_feature() -> None:
    """Skipped on Windows."""
    assert True


# Expected failure
@pytest.mark.xfail(reason="Known bug, fix in progress")
def test_known_failing() -> None:
    """Expected to fail - won't cause test suite failure."""
    assert 1 == 2


@pytest.mark.xfail(strict=True)
def test_must_fail() -> None:
    """If this passes, it's an error (strict xfail)."""
    assert 1 == 2


# Fixture for timeout (using pytest-timeout plugin)
# @pytest.mark.timeout(5)
# def test_with_timeout():
#     """Test must complete within 5 seconds."""
#     pass


# Custom marker with metadata
@pytest.mark.feature("authentication")
@pytest.mark.priority("high")
def test_login_flow() -> None:
    """Test with custom metadata markers."""
    assert True


class TestUserWorkflows:
    """Group related tests in a class."""

    @pytest.mark.smoke
    def test_user_creation(self) -> None:
        """Critical: verify user creation works."""
        assert True

    @pytest.mark.slow
    @pytest.mark.integration
    def test_user_bulk_import(self) -> None:
        """Slow integration test for bulk operations."""
        assert True


# Fixture that runs only for specific markers
@pytest.fixture
def expensive_resource(request) -> Generator[str, None, None]:
    """Only set up for integration tests."""
    marker = request.node.get_closest_marker("integration")
    if marker is None:
        pytest.skip("Only for integration tests")
    yield "expensive_resource"


def test_uses_expensive_resource(expensive_resource: str) -> None:
    """This test is skipped without integration marker."""
    assert expensive_resource == "expensive_resource"


@pytest.mark.integration
def test_with_expensive_resource(expensive_resource: str) -> None:
    """This test runs with the expensive resource."""
    assert expensive_resource == "expensive_resource"
```

**Running tests with markers**:
```bash
# Run only smoke tests
pytest -m smoke

# Run slow OR integration tests
pytest -m "slow or integration"

# Exclude slow tests
pytest -m "not slow"

# Complex marker expressions
pytest -m "smoke and not integration"
```

**Key points**:
- Register markers in `pyproject.toml` to avoid warnings
- Use `@pytest.mark.skip` for unconditional skip, `skipif` for conditional
- `xfail` marks expected failures; `strict=True` fails if test passes

---

### Example 4: Async Testing with pytest-asyncio

**Use case**: Test asynchronous code with proper event loop management.

```python
#!/usr/bin/env python3
"""Async testing with pytest-asyncio."""

import asyncio
import pytest
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock


@dataclass
class AsyncAPIClient:
    """Simulated async API client."""

    base_url: str
    timeout: float = 30.0

    async def get(self, path: str) -> dict[str, Any]:
        """Simulate async GET request."""
        await asyncio.sleep(0.01)  # Simulate network delay
        return {"path": path, "status": "ok"}

    async def post(self, path: str, data: dict) -> dict[str, Any]:
        """Simulate async POST request."""
        await asyncio.sleep(0.01)
        return {"path": path, "data": data, "status": "created"}


class AsyncUserService:
    """Service with async operations."""

    def __init__(self, client: AsyncAPIClient) -> None:
        self.client = client

    async def get_user(self, user_id: int) -> dict[str, Any]:
        """Fetch user by ID."""
        return await self.client.get(f"/users/{user_id}")

    async def create_user(self, name: str, email: str) -> dict[str, Any]:
        """Create a new user."""
        return await self.client.post("/users", {"name": name, "email": email})

    async def get_users_batch(self, user_ids: list[int]) -> list[dict[str, Any]]:
        """Fetch multiple users concurrently."""
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(self.get_user(uid)) for uid in user_ids]
        return [task.result() for task in tasks]


# Basic async test
@pytest.mark.asyncio
async def test_async_get() -> None:
    """Test basic async operation."""
    client = AsyncAPIClient(base_url="https://api.example.com")
    result = await client.get("/health")
    assert result["status"] == "ok"


# Async fixture
@pytest.fixture
async def api_client() -> AsyncAPIClient:
    """Async fixture for API client."""
    client = AsyncAPIClient(base_url="https://api.example.com")
    # Could do async setup here
    return client


@pytest.fixture
async def user_service(api_client: AsyncAPIClient) -> AsyncUserService:
    """Service fixture depending on async client fixture."""
    return AsyncUserService(api_client)


@pytest.mark.asyncio
async def test_get_user(user_service: AsyncUserService) -> None:
    """Test getting a user."""
    result = await user_service.get_user(123)
    assert result["path"] == "/users/123"


@pytest.mark.asyncio
async def test_create_user(user_service: AsyncUserService) -> None:
    """Test creating a user."""
    result = await user_service.create_user("Alice", "alice@example.com")
    assert result["status"] == "created"
    assert result["data"]["name"] == "Alice"


# Testing concurrent operations
@pytest.mark.asyncio
async def test_batch_fetch(user_service: AsyncUserService) -> None:
    """Test concurrent user fetching."""
    user_ids = [1, 2, 3, 4, 5]
    results = await user_service.get_users_batch(user_ids)
    assert len(results) == 5
    assert all(r["status"] == "ok" for r in results)


# Async mocking
@pytest.mark.asyncio
async def test_with_mock_client() -> None:
    """Test with mocked async client."""
    mock_client = AsyncMock(spec=AsyncAPIClient)
    mock_client.get.return_value = {"user_id": 1, "name": "Mocked User"}

    service = AsyncUserService(mock_client)
    result = await service.get_user(1)

    assert result["name"] == "Mocked User"
    mock_client.get.assert_called_once_with("/users/1")


# Testing timeouts
@pytest.mark.asyncio
async def test_timeout_handling() -> None:
    """Test that timeouts are handled properly."""

    async def slow_operation() -> str:
        await asyncio.sleep(10)
        return "done"

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.1):
            await slow_operation()


# Testing exception handling in async code
@pytest.mark.asyncio
async def test_async_exception() -> None:
    """Test exception handling in async context."""

    async def failing_operation() -> None:
        await asyncio.sleep(0.01)
        raise ValueError("Async operation failed")

    with pytest.raises(ValueError, match="Async operation failed"):
        await failing_operation()


# Parametrized async tests
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id,expected_path",
    [
        (1, "/users/1"),
        (42, "/users/42"),
        (999, "/users/999"),
    ],
)
async def test_get_user_paths(
    user_service: AsyncUserService, user_id: int, expected_path: str
) -> None:
    """Parametrized async test."""
    result = await user_service.get_user(user_id)
    assert result["path"] == expected_path


# Test TaskGroup exception handling
@pytest.mark.asyncio
async def test_taskgroup_partial_failure() -> None:
    """Test handling partial failures in TaskGroup."""

    async def maybe_fail(value: int) -> int:
        await asyncio.sleep(0.01)
        if value == 3:
            raise ValueError(f"Failed for {value}")
        return value * 2

    with pytest.raises(ExceptionGroup) as exc_info:
        async with asyncio.TaskGroup() as tg:
            for i in range(5):
                tg.create_task(maybe_fail(i))

    # Check that ValueError is in the exception group
    assert any(isinstance(e, ValueError) for e in exc_info.value.exceptions)
```

**Configuration in pyproject.toml**:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Automatically mark async tests
asyncio_default_fixture_loop_scope = "function"
```

**Key points**:
- Use `@pytest.mark.asyncio` or set `asyncio_mode = "auto"` in config
- `AsyncMock` from unittest.mock handles async method mocking
- Async fixtures work seamlessly with async tests

---

## Common Patterns

### Pattern: conftest.py for Shared Fixtures
```python
# conftest.py - automatically loaded by pytest
import pytest

@pytest.fixture(scope="session")
def app_config():
    """Session-wide configuration."""
    return {"debug": True, "database_url": "sqlite:///:memory:"}

@pytest.fixture
def client(app_config):
    """Test client available to all tests in directory."""
    return TestClient(app_config)
```

### Pattern: Temporary Files and Directories
```python
def test_file_processing(tmp_path):
    """tmp_path is a built-in fixture providing temp directory."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = process_file(test_file)
    assert result.success

def test_with_temp_file(tmp_path_factory):
    """Factory for creating multiple temp directories."""
    dir1 = tmp_path_factory.mktemp("data1")
    dir2 = tmp_path_factory.mktemp("data2")
```

### Pattern: Capturing Output
```python
def test_logging(caplog):
    """Capture log messages."""
    import logging
    logging.warning("Test warning")
    assert "Test warning" in caplog.text

def test_stdout(capsys):
    """Capture stdout/stderr."""
    print("Hello")
    captured = capsys.readouterr()
    assert captured.out == "Hello\n"
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Shared mutable state between tests
test_data = []

def test_one():
    test_data.append(1)
    assert len(test_data) == 1

def test_two():
    # Fails! test_data still has [1] from previous test
    assert len(test_data) == 0
```

**Do this instead:**
```python
@pytest.fixture
def test_data():
    """Fresh list for each test."""
    return []

def test_one(test_data):
    test_data.append(1)
    assert len(test_data) == 1

def test_two(test_data):
    # Works! Fresh list from fixture
    assert len(test_data) == 0
```

---

**Don't do this:**
```python
# Using time.sleep in async tests
@pytest.mark.asyncio
async def test_async_with_blocking_sleep():
    time.sleep(1)  # Blocks the event loop!
```

**Do this instead:**
```python
@pytest.mark.asyncio
async def test_async_properly():
    await asyncio.sleep(1)  # Non-blocking
```

---

## See Also

- [mocking-strategies.md](mocking-strategies.md) - Test doubles and isolation
- [property-testing.md](property-testing.md) - Hypothesis for generative testing
- [async-programming.md](../patterns/async-programming.md) - Async patterns
