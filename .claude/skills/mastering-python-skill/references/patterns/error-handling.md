# Error Handling, Debugging, and Logging

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Custom Exception Hierarchy](#example-1-custom-exception-hierarchy)
  - [Example 2: Structured Logging with structlog](#example-2-structured-logging-with-structlog)
  - [Example 3: Circuit Breaker Pattern](#example-3-circuit-breaker-pattern)
  - [Example 4: Retry with Exponential Backoff](#example-4-retry-with-exponential-backoff)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Basic try/except | `try: ... except ValueError as e: ...` |
| Multiple exceptions | `except (TypeError, ValueError):` |
| Re-raise with context | `raise NewError("msg") from original` |
| Finally cleanup | `try: ... finally: cleanup()` |
| Suppress exception | `with contextlib.suppress(FileNotFoundError):` |
| Assert with message | `assert condition, "Error message"` |
| Log exception | `logger.exception("Failed", exc_info=True)` |
| Exception groups | `except* ValueError as eg: ...` |

---

## Core Concepts

Effective error handling separates recoverable errors from programming bugs:

- **Exceptions**: Runtime errors that can be caught and handled
- **Custom Exceptions**: Domain-specific errors with rich context
- **Exception Chaining**: Preserve original cause with `raise ... from`
- **Logging**: Record errors with context for debugging
- **Retry Logic**: Handle transient failures gracefully

Python 3.11+ introduced exception groups for handling multiple simultaneous errors with `except*` syntax.

---

## Production Examples

### Example 1: Custom Exception Hierarchy

**Use case**: Create domain-specific exceptions with rich error context.

```python
#!/usr/bin/env python3
"""Custom exception hierarchy for a payment service."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ErrorCode(Enum):
    """Standardized error codes for API responses."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    RATE_LIMITED = "RATE_LIMITED"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class ErrorContext:
    """Rich context for error tracking."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ServiceError(Exception):
    """Base exception for all service errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        context: ErrorContext | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context or ErrorContext()

    def to_dict(self) -> dict[str, Any]:
        """Convert to API response format."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "timestamp": self.context.timestamp.isoformat(),
                "correlation_id": self.context.correlation_id,
            }
        }


class ValidationError(ServiceError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        context: ErrorContext | None = None,
    ) -> None:
        super().__init__(message, ErrorCode.VALIDATION_ERROR, context)
        self.field = field
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["error"]["field"] = self.field
        return result


class NotFoundError(ServiceError):
    """Raised when a resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        context: ErrorContext | None = None,
    ) -> None:
        message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(message, ErrorCode.NOT_FOUND, context)
        self.resource_type = resource_type
        self.resource_id = resource_id


class InsufficientFundsError(ServiceError):
    """Raised when account has insufficient funds."""

    def __init__(
        self,
        account_id: str,
        required: float,
        available: float,
        context: ErrorContext | None = None,
    ) -> None:
        message = f"Insufficient funds: required {required}, available {available}"
        super().__init__(message, ErrorCode.INSUFFICIENT_FUNDS, context)
        self.account_id = account_id
        self.required = required
        self.available = available


class ExternalServiceError(ServiceError):
    """Raised when an external service fails."""

    def __init__(
        self,
        service_name: str,
        original_error: Exception | None = None,
        context: ErrorContext | None = None,
    ) -> None:
        message = f"External service '{service_name}' failed"
        super().__init__(message, ErrorCode.EXTERNAL_SERVICE_ERROR, context)
        self.service_name = service_name
        self.original_error = original_error


# Usage example
def process_payment(user_id: str, amount: float, account_id: str) -> None:
    """Process a payment with proper error handling."""
    ctx = ErrorContext(user_id=user_id, correlation_id="req-123")

    # Validation
    if amount <= 0:
        raise ValidationError(
            "Amount must be positive",
            field="amount",
            value=amount,
            context=ctx,
        )

    # Check account exists
    account = get_account(account_id)
    if account is None:
        raise NotFoundError("Account", account_id, context=ctx)

    # Check funds
    if account.balance < amount:
        raise InsufficientFundsError(
            account_id=account_id,
            required=amount,
            available=account.balance,
            context=ctx,
        )


def get_account(account_id: str) -> Any:
    """Stub for account lookup."""
    return None


if __name__ == "__main__":
    try:
        process_payment("user-1", 100.0, "acc-123")
    except NotFoundError as e:
        print(f"Error: {e.to_dict()}")
    except ValidationError as e:
        print(f"Validation failed: {e.field} = {e.value}")
    except ServiceError as e:
        print(f"Service error: {e.code.value} - {e.message}")
```

**Key points**:
- Base exception class provides common structure
- Subclasses add domain-specific attributes
- `to_dict()` enables consistent API responses
- `ErrorContext` carries correlation IDs for tracing

---

### Example 2: Structured Logging with structlog

**Use case**: Configure production-grade structured logging.

```python
#!/usr/bin/env python3
"""Structured logging configuration with structlog."""

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON (for production)
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Choose processors based on environment
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_output:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger bound with the module name."""
    return structlog.get_logger(name)


# Usage example
class PaymentService:
    """Service with structured logging."""

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    def process_payment(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Process payment with comprehensive logging."""
        # Bind context for all subsequent logs
        log = self.logger.bind(
            user_id=user_id,
            amount=amount,
            currency=currency,
        )

        log.info("payment_started")

        try:
            # Simulate validation
            if amount <= 0:
                log.warning("payment_validation_failed", reason="invalid_amount")
                raise ValueError("Amount must be positive")

            # Simulate processing
            result = {"transaction_id": "txn-123", "status": "completed"}

            log.info(
                "payment_completed",
                transaction_id=result["transaction_id"],
            )
            return result

        except Exception as e:
            log.exception(
                "payment_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise


if __name__ == "__main__":
    # Development mode with colored output
    configure_logging(level="DEBUG", json_output=False)

    service = PaymentService()

    # Successful payment
    try:
        result = service.process_payment("user-123", 50.0)
        print(f"Result: {result}")
    except Exception:
        pass

    # Failed payment
    try:
        service.process_payment("user-456", -10.0)
    except ValueError:
        pass
```

**Key points**:
- Use `structlog` for JSON-compatible structured logs
- Bind context once, reuse across log calls
- Switch between dev (colored) and prod (JSON) output
- Always log `error_type` and `error_message` on exceptions

---

### Example 3: Circuit Breaker Pattern

**Use case**: Prevent cascading failures when external services are down.

```python
#!/usr/bin/env python3
"""Circuit breaker pattern for resilient external service calls."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for external service calls.

    Attributes:
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds before trying again
        success_threshold: Successes needed to close circuit
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for timeout."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function through circuit breaker."""
        state = self.state

        if state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit is open. Retry after {self.recovery_timeout}s"
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        else:
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN


class CircuitOpenError(Exception):
    """Raised when circuit is open and rejecting requests."""

    pass


# Decorator version
def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to wrap function with circuit breaker."""
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return breaker.call(func, *args, **kwargs)

        wrapper._circuit_breaker = breaker  # type: ignore
        return wrapper

    return decorator


# Usage example
@circuit_breaker(failure_threshold=3, recovery_timeout=10.0)
def call_external_api(endpoint: str) -> dict[str, Any]:
    """Call external API with circuit breaker protection."""
    # Simulate API call
    import random

    if random.random() < 0.5:
        raise ConnectionError("Service unavailable")
    return {"status": "ok", "endpoint": endpoint}


if __name__ == "__main__":
    for i in range(10):
        try:
            result = call_external_api("/api/data")
            print(f"Call {i}: Success - {result}")
        except CircuitOpenError as e:
            print(f"Call {i}: Circuit open - {e}")
        except ConnectionError as e:
            print(f"Call {i}: Failed - {e}")
        time.sleep(0.5)
```

**Key points**:
- Three states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
- Track failures and automatically open circuit
- Recovery timeout allows gradual retry
- Use decorator for clean integration

---

### Example 4: Retry with Exponential Backoff

**Use case**: Retry transient failures with increasing delays.

```python
#!/usr/bin/env python3
"""Retry logic with exponential backoff using tenacity."""

import random
from typing import Any

from tenacity import (
    RetryError,
    Retrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_random_exponential,
    before_sleep_log,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Simple decorator usage
@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def fetch_with_retry(url: str) -> dict[str, Any]:
    """Fetch URL with automatic retry on network errors."""
    if random.random() < 0.7:
        raise ConnectionError("Network error")
    return {"url": url, "status": "ok"}


# Advanced configuration
@retry(
    retry=retry_if_exception_type(Exception),
    stop=(stop_after_attempt(5) | stop_after_delay(30)),
    wait=wait_random_exponential(multiplier=1, max=60),
    reraise=True,
)
def critical_operation() -> str:
    """Critical operation with comprehensive retry config."""
    if random.random() < 0.8:
        raise RuntimeError("Transient error")
    return "success"


# Programmatic retry control
def fetch_with_manual_retry(url: str) -> dict[str, Any]:
    """Manual retry loop for more control."""
    for attempt in Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    ):
        with attempt:
            if random.random() < 0.7:
                raise ConnectionError(f"Failed to fetch {url}")
            return {"url": url, "data": "..."}

    # This is unreachable but satisfies type checker
    raise RetryError(None)  # type: ignore


# Conditional retry based on response
@retry(
    retry=retry_if_exception_type(ConnectionError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
def fetch_with_validation(url: str) -> dict[str, Any]:
    """Retry on both exceptions and invalid responses."""
    response = {"status": random.choice(["ok", "error", "rate_limited"])}

    if response["status"] == "rate_limited":
        raise ConnectionError("Rate limited, retry")
    if response["status"] == "error":
        raise ValueError("Permanent error, don't retry")

    return response


if __name__ == "__main__":
    # Test simple retry
    try:
        result = fetch_with_retry("https://api.example.com")
        print(f"Result: {result}")
    except ConnectionError:
        print("All retries exhausted")

    # Test manual retry
    try:
        result = fetch_with_manual_retry("https://api.example.com")
        print(f"Manual result: {result}")
    except RetryError:
        print("Manual retries exhausted")
```

**Key points**:
- `tenacity` provides declarative retry configuration
- Combine stop conditions with `|` (OR)
- Use `wait_random_exponential` to avoid thundering herd
- `before_sleep_log` logs retry attempts

---

## Common Patterns

### Pattern: Exception Chaining
```python
try:
    parse_config(data)
except json.JSONDecodeError as e:
    raise ConfigurationError(f"Invalid config: {e}") from e
```

### Pattern: Suppress Specific Exceptions
```python
from contextlib import suppress

with suppress(FileNotFoundError):
    os.remove(temp_file)
```

### Pattern: Exception Groups (Python 3.11+)
```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task1())
        tg.create_task(task2())
except* ValueError as eg:
    for exc in eg.exceptions:
        print(f"ValueError: {exc}")
except* TypeError as eg:
    for exc in eg.exceptions:
        print(f"TypeError: {exc}")
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Catching and silencing all exceptions
try:
    do_something()
except Exception:
    pass  # Silent failure - bugs become invisible
```

**Do this instead:**
```python
try:
    do_something()
except SpecificError as e:
    logger.warning("Expected error", error=str(e))
    return default_value
except Exception as e:
    logger.exception("Unexpected error")
    raise
```

---

**Don't do this:**
```python
# Losing the original exception context
try:
    parse_data(raw)
except ValueError:
    raise RuntimeError("Parse failed")  # Lost original traceback!
```

**Do this instead:**
```python
try:
    parse_data(raw)
except ValueError as e:
    raise RuntimeError("Parse failed") from e  # Preserves context
```

---

## See Also

- [async-programming.md](async-programming.md) - Exception groups with asyncio
- [monitoring.md](../production/monitoring.md) - Production logging and tracing
- [pytest-essentials.md](../testing/pytest-essentials.md) - Testing exceptions
