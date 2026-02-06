# Mocking Strategies

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Test Doubles Types](#example-1-test-doubles-types)
  - [Example 2: Mocking External Services](#example-2-mocking-external-services)
  - [Example 3: AsyncMock for Async Code](#example-3-asyncmock-for-async-code)
  - [Example 4: Patching and Context Managers](#example-4-patching-and-context-managers)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Create mock | `mock = Mock()` |
| Mock with spec | `mock = Mock(spec=MyClass)` |
| Mock return value | `mock.method.return_value = "value"` |
| Mock side effect | `mock.method.side_effect = ValueError("error")` |
| Patch object | `@patch("module.ClassName")` |
| Patch as context | `with patch("module.func") as mock:` |
| Assert called | `mock.method.assert_called_once()` |
| Assert call args | `mock.method.assert_called_with(arg1, arg2)` |
| Async mock | `mock = AsyncMock()` |
| Check call count | `assert mock.call_count == 3` |
| Reset mock | `mock.reset_mock()` |

---

## Core Concepts

Test doubles replace real dependencies during testing. The five types are:

1. **Dummy**: Placeholder that's never used, just fills parameter requirements
2. **Fake**: Working implementation with shortcuts (in-memory database)
3. **Stub**: Returns predetermined responses, no behavior verification
4. **Spy**: Records calls while delegating to real implementation
5. **Mock**: Verifies interactions and can specify expected behavior

**When to mock**:
- External services (APIs, databases, file systems)
- Non-deterministic behavior (time, random)
- Slow operations (network calls, heavy computation)
- Operations with side effects (sending emails, payments)

**When NOT to mock**:
- Simple value objects and data classes
- Pure functions with no side effects
- The code under test itself

---

## Production Examples

### Example 1: Test Doubles Types

**Use case**: Understanding different test double types and when to use each.

```python
#!/usr/bin/env python3
"""Different types of test doubles demonstrated."""

from dataclasses import dataclass
from typing import Protocol
from unittest.mock import Mock, MagicMock, call


# Interface for our examples
class EmailService(Protocol):
    """Email service interface."""

    def send(self, to: str, subject: str, body: str) -> bool: ...
    def get_sent_count(self) -> int: ...


class PaymentProcessor(Protocol):
    """Payment processor interface."""

    def charge(self, amount: float, card_token: str) -> str: ...


@dataclass
class Order:
    """Order that needs email and payment services."""

    id: str
    customer_email: str
    amount: float

    def process(
        self, email_service: EmailService, payment: PaymentProcessor
    ) -> dict:
        """Process order with payment and notification."""
        transaction_id = payment.charge(self.amount, "card_token")
        email_service.send(
            self.customer_email,
            f"Order {self.id} Confirmed",
            f"Transaction: {transaction_id}",
        )
        return {"order_id": self.id, "transaction_id": transaction_id}


# 1. DUMMY - placeholder, never actually used
def test_with_dummy() -> None:
    """Dummy is passed but never used."""

    def generate_report(data: list, logger=None) -> str:
        # logger is never used in this code path
        return f"Report: {len(data)} items"

    dummy_logger = None  # or Mock() - doesn't matter, it's not called
    result = generate_report([1, 2, 3], dummy_logger)
    assert result == "Report: 3 items"


# 2. FAKE - working implementation with shortcuts
class FakeEmailService:
    """Fake email service that stores emails in memory."""

    def __init__(self) -> None:
        self.sent_emails: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> bool:
        self.sent_emails.append({"to": to, "subject": subject, "body": body})
        return True

    def get_sent_count(self) -> int:
        return len(self.sent_emails)


def test_with_fake() -> None:
    """Fake has working implementation but simpler than production."""
    fake_email = FakeEmailService()
    fake_payment = Mock(spec=PaymentProcessor)
    fake_payment.charge.return_value = "txn_123"

    order = Order(id="order_1", customer_email="test@example.com", amount=99.99)
    result = order.process(fake_email, fake_payment)

    # Verify using fake's internal state
    assert fake_email.get_sent_count() == 1
    assert fake_email.sent_emails[0]["to"] == "test@example.com"
    assert "txn_123" in fake_email.sent_emails[0]["body"]


# 3. STUB - returns predetermined responses
def test_with_stub() -> None:
    """Stub returns canned responses, no verification."""
    stub_email = Mock(spec=EmailService)
    stub_email.send.return_value = True
    stub_email.get_sent_count.return_value = 1

    stub_payment = Mock(spec=PaymentProcessor)
    stub_payment.charge.return_value = "txn_stub_456"

    order = Order(id="order_2", customer_email="stub@example.com", amount=50.00)
    result = order.process(stub_email, stub_payment)

    # Only verify the result, not how stubs were called
    assert result["transaction_id"] == "txn_stub_456"


# 4. SPY - records calls while using real implementation
class SpyEmailService:
    """Spy wraps real service and records calls."""

    def __init__(self, real_service: EmailService) -> None:
        self.real_service = real_service
        self.calls: list[tuple] = []

    def send(self, to: str, subject: str, body: str) -> bool:
        self.calls.append(("send", to, subject, body))
        return self.real_service.send(to, subject, body)

    def get_sent_count(self) -> int:
        self.calls.append(("get_sent_count",))
        return self.real_service.get_sent_count()


def test_with_spy() -> None:
    """Spy delegates to real implementation but records calls."""
    real_email = FakeEmailService()  # Using fake as "real" for demo
    spy_email = SpyEmailService(real_email)

    mock_payment = Mock(spec=PaymentProcessor)
    mock_payment.charge.return_value = "txn_spy_789"

    order = Order(id="order_3", customer_email="spy@example.com", amount=25.00)
    order.process(spy_email, mock_payment)

    # Verify calls were recorded
    assert len(spy_email.calls) == 1
    assert spy_email.calls[0][0] == "send"
    assert spy_email.calls[0][1] == "spy@example.com"

    # And real implementation was called
    assert real_email.get_sent_count() == 1


# 5. MOCK - verifies interactions
def test_with_mock() -> None:
    """Mock verifies expected interactions occurred."""
    mock_email = Mock(spec=EmailService)
    mock_email.send.return_value = True

    mock_payment = Mock(spec=PaymentProcessor)
    mock_payment.charge.return_value = "txn_mock_000"

    order = Order(id="order_4", customer_email="mock@example.com", amount=100.00)
    order.process(mock_email, mock_payment)

    # Verify interactions with mock
    mock_payment.charge.assert_called_once_with(100.00, "card_token")
    mock_email.send.assert_called_once()

    # Verify call arguments in detail
    call_args = mock_email.send.call_args
    assert call_args[0][0] == "mock@example.com"  # positional arg: to
    assert "Order order_4" in call_args[0][1]  # positional arg: subject
```

**Key points**:
- Use `spec=` to ensure mock only allows methods that exist on real class
- Fakes are useful when you need working behavior (in-memory databases)
- Mocks are best for verifying interactions with external services

---

### Example 2: Mocking External Services

**Use case**: Test code that depends on HTTP APIs without making real requests.

```python
#!/usr/bin/env python3
"""Mocking HTTP clients and external services."""

import pytest
from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock, patch, MagicMock
import json


@dataclass
class WeatherData:
    """Weather data from API."""

    city: str
    temperature: float
    conditions: str


class WeatherService:
    """Service that fetches weather from external API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.weather.com"

    def get_weather(self, city: str) -> WeatherData:
        """Fetch weather for a city."""
        import requests

        response = requests.get(
            f"{self.base_url}/current",
            params={"city": city, "key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return WeatherData(
            city=data["location"]["name"],
            temperature=data["current"]["temp_c"],
            conditions=data["current"]["condition"]["text"],
        )

    def get_forecast(self, city: str, days: int = 3) -> list[dict[str, Any]]:
        """Fetch multi-day forecast."""
        import requests

        response = requests.get(
            f"{self.base_url}/forecast",
            params={"city": city, "days": days, "key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["forecast"]["forecastday"]


class TestWeatherServiceMocking:
    """Tests demonstrating various mocking approaches."""

    def test_mock_requests_get(self) -> None:
        """Mock requests.get directly."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "location": {"name": "London"},
            "current": {"temp_c": 15.5, "condition": {"text": "Cloudy"}},
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response) as mock_get:
            service = WeatherService(api_key="test_key")
            result = service.get_weather("London")

            assert result.city == "London"
            assert result.temperature == 15.5
            assert result.conditions == "Cloudy"

            # Verify the request was made correctly
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["params"]["city"] == "London"
            assert call_kwargs["params"]["key"] == "test_key"

    def test_mock_response_with_error(self) -> None:
        """Test error handling with mocked response."""
        import requests

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with patch("requests.get", return_value=mock_response):
            service = WeatherService(api_key="test_key")

            with pytest.raises(requests.HTTPError):
                service.get_weather("NonexistentCity")

    def test_mock_with_side_effect_sequence(self) -> None:
        """Mock returning different values on successive calls."""

        def create_response(temp: float) -> Mock:
            mock = Mock()
            mock.json.return_value = {
                "location": {"name": "Paris"},
                "current": {"temp_c": temp, "condition": {"text": "Sunny"}},
            }
            mock.raise_for_status = Mock()
            return mock

        # Return different temperatures on each call
        with patch(
            "requests.get",
            side_effect=[create_response(20.0), create_response(22.0)],
        ):
            service = WeatherService(api_key="test_key")

            result1 = service.get_weather("Paris")
            result2 = service.get_weather("Paris")

            assert result1.temperature == 20.0
            assert result2.temperature == 22.0

    def test_mock_with_fixture(self, mocker) -> None:
        """Use pytest-mock's mocker fixture for cleaner syntax."""
        # mocker is from pytest-mock plugin
        mock_response = mocker.Mock()
        mock_response.json.return_value = {
            "location": {"name": "Berlin"},
            "current": {"temp_c": 18.0, "condition": {"text": "Clear"}},
        }
        mock_response.raise_for_status = mocker.Mock()

        mocker.patch("requests.get", return_value=mock_response)

        service = WeatherService(api_key="test_key")
        result = service.get_weather("Berlin")

        assert result.city == "Berlin"


# Using responses library for more realistic HTTP mocking
class TestWithResponsesLibrary:
    """Tests using the responses library (more realistic HTTP mocking)."""

    def test_with_responses_mock(self) -> None:
        """Mock HTTP with responses library."""
        import responses
        import requests

        @responses.activate
        def run_test():
            # Register mock response
            responses.add(
                responses.GET,
                "https://api.weather.com/current",
                json={
                    "location": {"name": "Tokyo"},
                    "current": {"temp_c": 25.0, "condition": {"text": "Humid"}},
                },
                status=200,
            )

            service = WeatherService(api_key="test_key")
            result = service.get_weather("Tokyo")

            assert result.city == "Tokyo"
            assert result.temperature == 25.0

            # Verify request was made
            assert len(responses.calls) == 1
            assert "city=Tokyo" in responses.calls[0].request.url

        # Note: Would run if responses library is installed
        # run_test()


# Mocking at different levels
class TestMockingLevels:
    """Demonstrate mocking at different abstraction levels."""

    def test_mock_at_boundary(self) -> None:
        """Mock at the service boundary - recommended approach."""
        # Create a mock of the entire service
        mock_service = Mock(spec=WeatherService)
        mock_service.get_weather.return_value = WeatherData(
            city="Moscow", temperature=5.0, conditions="Snowy"
        )

        # Code that uses the service
        def get_weather_summary(service: WeatherService, city: str) -> str:
            data = service.get_weather(city)
            return f"{data.city}: {data.temperature}°C, {data.conditions}"

        result = get_weather_summary(mock_service, "Moscow")
        assert result == "Moscow: 5.0°C, Snowy"

    def test_mock_only_external_call(self) -> None:
        """Mock only the HTTP call, test service logic."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "location": {"name": "Sydney"},
            "current": {"temp_c": 28.0, "condition": {"text": "Hot"}},
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            # Test real service logic with mocked HTTP
            service = WeatherService(api_key="real_key")
            result = service.get_weather("Sydney")

            # Service parsing logic is tested
            assert isinstance(result, WeatherData)
            assert result.city == "Sydney"
```

**Key points**:
- Mock at the boundary (HTTP layer) to test service logic
- Use `side_effect` for sequences or exceptions
- `responses` library provides more realistic HTTP mocking

---

### Example 3: AsyncMock for Async Code

**Use case**: Mock asynchronous methods and coroutines.

```python
#!/usr/bin/env python3
"""Mocking async code with AsyncMock."""

import asyncio
import pytest
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, Mock, patch, MagicMock


@dataclass
class AsyncAPIClient:
    """Async HTTP client."""

    base_url: str

    async def get(self, path: str) -> dict[str, Any]:
        """Make async GET request."""
        # Real implementation would use aiohttp
        raise NotImplementedError("Use mock in tests")

    async def post(self, path: str, data: dict) -> dict[str, Any]:
        """Make async POST request."""
        raise NotImplementedError("Use mock in tests")


class UserRepository:
    """Repository with async database operations."""

    def __init__(self, client: AsyncAPIClient) -> None:
        self.client = client

    async def get_user(self, user_id: int) -> dict[str, Any]:
        """Fetch user by ID."""
        return await self.client.get(f"/users/{user_id}")

    async def create_user(self, name: str, email: str) -> dict[str, Any]:
        """Create new user."""
        return await self.client.post("/users", {"name": name, "email": email})

    async def get_users_batch(self, user_ids: list[int]) -> list[dict[str, Any]]:
        """Fetch multiple users concurrently."""
        tasks = [self.get_user(uid) for uid in user_ids]
        return await asyncio.gather(*tasks)


class TestAsyncMocking:
    """Tests for async code mocking."""

    @pytest.mark.asyncio
    async def test_basic_async_mock(self) -> None:
        """Basic AsyncMock usage."""
        mock_client = AsyncMock(spec=AsyncAPIClient)
        mock_client.get.return_value = {"id": 1, "name": "Alice"}

        repo = UserRepository(mock_client)
        result = await repo.get_user(1)

        assert result["name"] == "Alice"
        mock_client.get.assert_called_once_with("/users/1")

    @pytest.mark.asyncio
    async def test_async_mock_with_side_effect(self) -> None:
        """AsyncMock with side_effect for exceptions."""
        mock_client = AsyncMock(spec=AsyncAPIClient)
        mock_client.get.side_effect = ConnectionError("Network error")

        repo = UserRepository(mock_client)

        with pytest.raises(ConnectionError, match="Network error"):
            await repo.get_user(1)

    @pytest.mark.asyncio
    async def test_async_mock_sequence(self) -> None:
        """AsyncMock returning different values on each call."""
        mock_client = AsyncMock(spec=AsyncAPIClient)
        mock_client.get.side_effect = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]

        repo = UserRepository(mock_client)

        # Each call returns next value in sequence
        result1 = await repo.get_user(1)
        result2 = await repo.get_user(2)
        result3 = await repo.get_user(3)

        assert result1["name"] == "Alice"
        assert result2["name"] == "Bob"
        assert result3["name"] == "Charlie"

    @pytest.mark.asyncio
    async def test_concurrent_async_calls(self) -> None:
        """Test concurrent async operations with mock."""
        mock_client = AsyncMock(spec=AsyncAPIClient)

        # Return different data based on path
        async def mock_get(path: str) -> dict[str, Any]:
            user_id = int(path.split("/")[-1])
            return {"id": user_id, "name": f"User{user_id}"}

        mock_client.get.side_effect = mock_get

        repo = UserRepository(mock_client)
        results = await repo.get_users_batch([1, 2, 3])

        assert len(results) == 3
        assert results[0]["name"] == "User1"
        assert results[2]["name"] == "User3"
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_async_context_manager_mock(self) -> None:
        """Mock async context manager."""

        class AsyncDBConnection:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def execute(self, query: str) -> list[dict]:
                raise NotImplementedError()

        # Create mock that works as async context manager
        mock_conn = AsyncMock(spec=AsyncDBConnection)
        mock_conn.__aenter__.return_value = mock_conn
        mock_conn.execute.return_value = [{"id": 1}]

        async with mock_conn as conn:
            result = await conn.execute("SELECT * FROM users")

        assert result == [{"id": 1}]
        mock_conn.__aenter__.assert_called_once()
        mock_conn.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_sync_and_async_mock(self) -> None:
        """Mock object with both sync and async methods."""

        class MixedService:
            def sync_method(self) -> str:
                return "sync"

            async def async_method(self) -> str:
                return "async"

        # MagicMock for sync, add AsyncMock for async
        mock_service = MagicMock(spec=MixedService)
        mock_service.sync_method.return_value = "mocked sync"
        mock_service.async_method = AsyncMock(return_value="mocked async")

        assert mock_service.sync_method() == "mocked sync"
        assert await mock_service.async_method() == "mocked async"

    @pytest.mark.asyncio
    async def test_assert_awaited(self) -> None:
        """Verify async methods were awaited."""
        mock_client = AsyncMock(spec=AsyncAPIClient)
        mock_client.get.return_value = {"id": 1}

        repo = UserRepository(mock_client)
        await repo.get_user(1)

        # assert_awaited variants
        mock_client.get.assert_awaited()
        mock_client.get.assert_awaited_once()
        mock_client.get.assert_awaited_with("/users/1")

    @pytest.mark.asyncio
    async def test_patch_async_function(self) -> None:
        """Patch an async function."""

        async def fetch_data(url: str) -> dict:
            raise NotImplementedError()

        async def process_data() -> str:
            data = await fetch_data("http://example.com")
            return data["result"]

        with patch(
            f"{__name__}.fetch_data",  # Would be actual module path
            new_callable=AsyncMock,
            return_value={"result": "processed"},
        ):
            # In real code, this would call the patched function
            pass
```

**Key points**:
- `AsyncMock` automatically handles `await` calls
- Use `assert_awaited*` methods to verify async calls
- `side_effect` works with async - can be a coroutine function

---

### Example 4: Patching and Context Managers

**Use case**: Control what code sees during execution using patch decorators and context managers.

```python
#!/usr/bin/env python3
"""Patching strategies with unittest.mock."""

import os
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, PropertyMock, call
from typing import Any


class ConfigLoader:
    """Loads configuration from environment and files."""

    def __init__(self) -> None:
        self.env = os.environ.get("APP_ENV", "development")

    def get_database_url(self) -> str:
        """Get database URL from environment."""
        return os.environ.get("DATABASE_URL", "sqlite:///default.db")

    def get_current_time(self) -> datetime:
        """Get current timestamp."""
        return datetime.now()

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == "production"


class NotificationService:
    """Service that sends notifications."""

    def __init__(self) -> None:
        self.sent_count = 0

    def send_email(self, to: str, subject: str) -> bool:
        """Send email notification."""
        # Real implementation would send email
        self.sent_count += 1
        return True

    def send_sms(self, phone: str, message: str) -> bool:
        """Send SMS notification."""
        self.sent_count += 1
        return True


def get_notification_service() -> NotificationService:
    """Factory function for notification service."""
    return NotificationService()


class TestPatchingStrategies:
    """Demonstrate various patching approaches."""

    # 1. Patch as decorator
    @patch("os.environ.get")
    def test_patch_decorator(self, mock_environ_get: MagicMock) -> None:
        """Patch using decorator - mock is passed as argument."""
        mock_environ_get.return_value = "production"

        loader = ConfigLoader()
        url = loader.get_database_url()

        assert url == "production"
        mock_environ_get.assert_called()

    # 2. Patch as context manager
    def test_patch_context_manager(self) -> None:
        """Patch using context manager - more explicit scope."""
        with patch("os.environ.get") as mock_get:
            mock_get.return_value = "postgresql://prod-db"

            loader = ConfigLoader()
            url = loader.get_database_url()

            assert url == "postgresql://prod-db"

        # After context, os.environ.get is restored

    # 3. Patch multiple targets
    @patch("os.environ.get")
    @patch.object(datetime, "now")
    def test_multiple_patches(
        self, mock_now: MagicMock, mock_environ: MagicMock
    ) -> None:
        """Multiple patches - note reverse order of arguments!"""
        mock_environ.return_value = "test_db_url"
        mock_now.return_value = datetime(2024, 1, 15, 12, 0, 0)

        loader = ConfigLoader()
        time = loader.get_current_time()

        assert time == datetime(2024, 1, 15, 12, 0, 0)

    # 4. Patch with return value
    def test_patch_return_value(self) -> None:
        """Set return value directly in patch call."""
        with patch("os.environ.get", return_value="mocked_value"):
            result = os.environ.get("ANY_KEY")
            assert result == "mocked_value"

    # 5. Patch with side_effect for different calls
    def test_patch_side_effect_dict(self) -> None:
        """side_effect with dict maps arguments to return values."""

        def mock_environ_get(key: str, default: str = "") -> str:
            values = {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql://prod",
                "SECRET_KEY": "super-secret",
            }
            return values.get(key, default)

        with patch("os.environ.get", side_effect=mock_environ_get):
            assert os.environ.get("APP_ENV") == "production"
            assert os.environ.get("DATABASE_URL") == "postgresql://prod"
            assert os.environ.get("MISSING", "default") == "default"

    # 6. Patch a property
    def test_patch_property(self) -> None:
        """Patch a property using PropertyMock."""
        with patch.object(
            ConfigLoader, "is_production", new_callable=PropertyMock
        ) as mock_prop:
            mock_prop.return_value = True

            loader = ConfigLoader()
            assert loader.is_production is True

    # 7. Patch where it's used, not where it's defined
    def test_patch_where_used(self) -> None:
        """Important: Patch the name in the module that uses it."""
        # If module_a imports: from datetime import datetime
        # Patch 'module_a.datetime', not 'datetime.datetime'

        # In this file, datetime is imported directly
        with patch(f"{__name__}.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 6, 15)
            # Now any code in this module using datetime.now() gets mock

    # 8. Patch.dict for dictionaries
    def test_patch_dict(self) -> None:
        """Patch dictionary contents."""
        with patch.dict(os.environ, {"APP_ENV": "staging", "DEBUG": "true"}):
            assert os.environ["APP_ENV"] == "staging"
            assert os.environ["DEBUG"] == "true"

        # Original values restored after context

    def test_patch_dict_clear(self) -> None:
        """Patch dict with clear=True removes existing keys."""
        original_path = os.environ.get("PATH")

        with patch.dict(os.environ, {"ONLY_THIS": "value"}, clear=True):
            assert "PATH" not in os.environ
            assert os.environ["ONLY_THIS"] == "value"

        assert os.environ.get("PATH") == original_path

    # 9. Verify call order
    def test_call_order(self) -> None:
        """Verify methods were called in specific order."""
        mock_service = MagicMock(spec=NotificationService)

        # Simulate some operations
        mock_service.send_email("user@example.com", "Welcome")
        mock_service.send_sms("+1234567890", "Code: 1234")
        mock_service.send_email("user@example.com", "Reminder")

        # Verify call order
        expected_calls = [
            call.send_email("user@example.com", "Welcome"),
            call.send_sms("+1234567890", "Code: 1234"),
            call.send_email("user@example.com", "Reminder"),
        ]
        assert mock_service.method_calls == expected_calls

    # 10. Patch object method
    def test_patch_object_method(self) -> None:
        """Patch a specific method on an object."""
        service = NotificationService()

        with patch.object(service, "send_email", return_value=False) as mock_send:
            result = service.send_email("test@example.com", "Test")

            assert result is False
            mock_send.assert_called_once_with("test@example.com", "Test")

    # 11. Autospec for safety
    def test_autospec(self) -> None:
        """autospec creates mock matching the real object's signature."""
        with patch.object(
            NotificationService, "send_email", autospec=True
        ) as mock_send:
            mock_send.return_value = True

            service = NotificationService()
            # First arg is 'self' with autospec
            result = service.send_email("test@example.com", "Subject")

            assert result is True
            # autospec catches signature errors at test time
            # mock_send("wrong", "args", "count")  # Would raise TypeError

    # 12. Start/stop for manual control
    def test_manual_start_stop(self) -> None:
        """Manual patch control with start() and stop()."""
        patcher = patch("os.environ.get", return_value="manual_mock")

        # Patch not active yet
        mock = patcher.start()

        try:
            assert os.environ.get("ANY") == "manual_mock"
        finally:
            patcher.stop()

        # Patch no longer active


class TestPatchingWithPytestMock:
    """Tests using pytest-mock plugin (mocker fixture)."""

    def test_mocker_patch(self, mocker) -> None:
        """mocker fixture provides cleaner API."""
        mock_get = mocker.patch("os.environ.get", return_value="mocked")

        assert os.environ.get("KEY") == "mocked"
        mock_get.assert_called_once()

    def test_mocker_spy(self, mocker) -> None:
        """mocker.spy wraps real method but tracks calls."""
        service = NotificationService()
        spy = mocker.spy(service, "send_email")

        # Real method is called
        result = service.send_email("test@example.com", "Subject")

        assert result is True
        assert service.sent_count == 1  # Real side effect occurred
        spy.assert_called_once_with("test@example.com", "Subject")
```

**Key points**:
- Patch where the name is used, not where it's defined
- Use `autospec=True` to catch signature mismatches
- `patch.dict` is useful for environment variables
- pytest-mock's `mocker` fixture auto-cleans up patches

---

## Common Patterns

### Pattern: Dependency Injection for Testability
```python
# Hard to test - creates its own dependencies
class BadService:
    def __init__(self):
        self.client = RealHTTPClient()  # Hard-coded dependency

# Easy to test - accepts dependencies
class GoodService:
    def __init__(self, client: HTTPClient):
        self.client = client  # Inject mock in tests
```

### Pattern: Mock Builder
```python
def create_mock_response(
    status: int = 200,
    json_data: dict | None = None,
    raise_error: bool = False,
) -> MagicMock:
    """Factory for creating mock HTTP responses."""
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = json_data or {}
    if raise_error:
        mock.raise_for_status.side_effect = HTTPError()
    return mock
```

### Pattern: Freezing Time
```python
from freezegun import freeze_time

@freeze_time("2024-01-15 12:00:00")
def test_time_dependent_code():
    """All datetime calls return frozen time."""
    assert datetime.now() == datetime(2024, 1, 15, 12, 0, 0)
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Patching in wrong location
# If my_module does: from datetime import datetime
@patch("datetime.datetime")  # Wrong! Patches the source
def test_wrong_patch(mock_dt):
    pass

# Correct: patch where it's imported
@patch("my_module.datetime")  # Right! Patches where it's used
def test_correct_patch(mock_dt):
    pass
```

---

**Don't do this:**
```python
# Over-mocking - testing mocks, not code
def test_over_mocked():
    mock_service = Mock()
    mock_service.process.return_value = "result"

    result = mock_service.process("input")  # Just testing the mock!

    assert result == "result"  # This proves nothing
```

**Do this instead:**
```python
def test_properly_mocked():
    mock_client = Mock(spec=HTTPClient)
    mock_client.get.return_value = {"data": "value"}

    # Test REAL code with mocked dependency
    service = MyService(mock_client)
    result = service.process_data()  # Real logic under test

    assert result == "processed: value"
```

---

## See Also

- [pytest-essentials.md](pytest-essentials.md) - Core pytest patterns
- [property-testing.md](property-testing.md) - Generative testing with Hypothesis
- [async-programming.md](../patterns/async-programming.md) - Async patterns
