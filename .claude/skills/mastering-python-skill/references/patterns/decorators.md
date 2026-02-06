# Decorators

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Basic Function Decorators](#example-1-basic-function-decorators)
  - [Example 2: Decorators with Arguments](#example-2-decorators-with-arguments)
  - [Example 3: Class Decorators](#example-3-class-decorators)
  - [Example 4: Stacking and Composition](#example-4-stacking-and-composition)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Pattern | Code |
|---------|------|
| Basic decorator | `@decorator` above function |
| Preserve metadata | `@functools.wraps(func)` |
| With arguments | `@decorator(arg=value)` |
| Class decorator | `@dataclass` |
| Method decorator | `@staticmethod`, `@classmethod` |
| Property | `@property` |
| Stack decorators | Top decorator wraps bottom |

---

## Core Concepts

Decorators modify or enhance functions and classes without changing their source code:

- **Function Decorators**: Wrap functions to add behavior (logging, caching, validation)
- **Class Decorators**: Modify class definitions (add methods, register classes)
- **`@functools.wraps`**: Preserve original function metadata (name, docstring)
- **Parameterized Decorators**: Accept configuration arguments

Decorators are applied bottom-to-top when stacked:
```python
@decorator_a  # Applied second (wraps result of @decorator_b)
@decorator_b  # Applied first
def func(): ...
```

---

## Production Examples

### Example 1: Basic Function Decorators

**Use case**: Add logging, timing, and validation to functions.

```python
#!/usr/bin/env python3
"""Basic function decorators with proper metadata preservation."""

import functools
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def log_calls(func: Callable[..., T]) -> Callable[..., T]:
    """Log function calls with arguments and return values.

    Always use @functools.wraps to preserve the original
    function's name, docstring, and other metadata.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)

        print(f"Calling {func.__name__}({signature})")
        result = func(*args, **kwargs)
        print(f"{func.__name__} returned {result!r}")

        return result

    return wrapper


def timer(func: Callable[..., T]) -> Callable[..., T]:
    """Measure and print function execution time."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f} seconds")
        return result

    return wrapper


def validate_positive(func: Callable[..., T]) -> Callable[..., T]:
    """Ensure all numeric arguments are positive."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        for i, arg in enumerate(args):
            if isinstance(arg, (int, float)) and arg <= 0:
                raise ValueError(f"Argument {i} must be positive, got {arg}")
        for key, value in kwargs.items():
            if isinstance(value, (int, float)) and value <= 0:
                raise ValueError(f"Argument '{key}' must be positive, got {value}")
        return func(*args, **kwargs)

    return wrapper


# Usage examples
@log_calls
def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


@timer
def slow_operation(n: int) -> int:
    """Simulate a slow computation."""
    time.sleep(0.1)
    return sum(range(n))


@validate_positive
def calculate_area(width: float, height: float) -> float:
    """Calculate rectangle area."""
    return width * height


if __name__ == "__main__":
    # Test logging
    print(greet("Alice"))
    print(f"Function name: {greet.__name__}")
    print(f"Docstring: {greet.__doc__}")

    print()

    # Test timing
    result = slow_operation(1000)
    print(f"Result: {result}")

    print()

    # Test validation
    print(f"Area: {calculate_area(5.0, 3.0)}")

    try:
        calculate_area(-5.0, 3.0)
    except ValueError as e:
        print(f"Validation error: {e}")
```

**Key points**:
- Always use `@functools.wraps(func)` to preserve metadata
- Type hints with `TypeVar` maintain return type information
- Decorators can validate, log, time, or modify behavior

---

### Example 2: Decorators with Arguments

**Use case**: Create configurable decorators.

```python
#!/usr/bin/env python3
"""Decorators that accept configuration arguments."""

import functools
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a function on failure with configurable attempts and delay.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Seconds to wait between retries
        exceptions: Tuple of exception types to catch

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        print(f"Attempt {attempt} failed: {e}. Retrying...")
                        time.sleep(delay)
                    else:
                        print(f"Attempt {attempt} failed: {e}. No more retries.")

            raise last_exception  # type: ignore

        return wrapper

    return decorator


def rate_limit(
    calls: int,
    period: float,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Limit function calls to N calls per period seconds."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        call_times: list[float] = []

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            now = time.time()
            # Remove calls outside the time window
            call_times[:] = [t for t in call_times if now - t < period]

            if len(call_times) >= calls:
                wait_time = period - (now - call_times[0])
                raise RuntimeError(
                    f"Rate limit exceeded. Try again in {wait_time:.1f}s"
                )

            call_times.append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def cache(maxsize: int = 128, ttl: float | None = None) -> Callable:
    """Cache function results with optional TTL.

    Args:
        maxsize: Maximum cache entries
        ttl: Time-to-live in seconds (None = no expiry)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache_data: dict[tuple, tuple[T, float]] = {}

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Create hashable key
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()

            # Check cache
            if key in cache_data:
                result, timestamp = cache_data[key]
                if ttl is None or now - timestamp < ttl:
                    return result

            # Compute and cache
            result = func(*args, **kwargs)
            cache_data[key] = (result, now)

            # Evict oldest if over maxsize
            if len(cache_data) > maxsize:
                oldest_key = min(cache_data, key=lambda k: cache_data[k][1])
                del cache_data[oldest_key]

            return result

        # Add cache management methods
        wrapper.cache_clear = lambda: cache_data.clear()  # type: ignore
        wrapper.cache_info = lambda: {  # type: ignore
            "size": len(cache_data),
            "maxsize": maxsize,
        }

        return wrapper

    return decorator


# Usage examples
@retry(max_attempts=3, delay=0.5, exceptions=(ConnectionError,))
def fetch_data(url: str) -> str:
    """Fetch data with automatic retry."""
    import random

    if random.random() < 0.7:
        raise ConnectionError("Network error")
    return f"Data from {url}"


@rate_limit(calls=3, period=10.0)
def api_call(endpoint: str) -> dict:
    """Make an API call with rate limiting."""
    return {"endpoint": endpoint, "status": "ok"}


@cache(maxsize=100, ttl=60.0)
def expensive_computation(n: int) -> int:
    """Compute with caching."""
    time.sleep(0.1)  # Simulate expensive work
    return n * n


if __name__ == "__main__":
    # Test retry
    try:
        result = fetch_data("https://api.example.com")
        print(f"Fetch result: {result}")
    except ConnectionError:
        print("All retries failed")

    print()

    # Test caching
    print(f"First call: {expensive_computation(5)}")
    print(f"Cached call: {expensive_computation(5)}")
    print(f"Cache info: {expensive_computation.cache_info()}")
```

**Key points**:
- Parameterized decorators have three levels: outer function, decorator, wrapper
- Store state in closure variables (like `call_times`, `cache_data`)
- Add utility methods to wrapper function for cache management

---

### Example 3: Class Decorators

**Use case**: Modify class definitions or register classes.

```python
#!/usr/bin/env python3
"""Class decorators for modification and registration."""

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

T = TypeVar("T", bound=type)


def singleton(cls: T) -> T:
    """Make a class a singleton - only one instance ever created."""
    instances: dict[type, Any] = {}

    original_new = cls.__new__

    def new_method(cls: type, *args: Any, **kwargs: Any) -> Any:
        if cls not in instances:
            instance = original_new(cls)
            instances[cls] = instance
        return instances[cls]

    cls.__new__ = new_method  # type: ignore
    return cls


def auto_repr(cls: T) -> T:
    """Automatically generate __repr__ from __init__ parameters."""
    import inspect

    init_signature = inspect.signature(cls.__init__)
    params = [p for p in init_signature.parameters if p != "self"]

    def __repr__(self: Any) -> str:
        values = ", ".join(f"{p}={getattr(self, p)!r}" for p in params)
        return f"{cls.__name__}({values})"

    cls.__repr__ = __repr__  # type: ignore
    return cls


# Registry pattern
_plugin_registry: dict[str, type] = {}


def register_plugin(name: str) -> Callable[[T], T]:
    """Register a class as a plugin with a given name."""

    def decorator(cls: T) -> T:
        _plugin_registry[name] = cls
        return cls

    return decorator


def get_plugin(name: str) -> type | None:
    """Get a registered plugin by name."""
    return _plugin_registry.get(name)


def list_plugins() -> list[str]:
    """List all registered plugin names."""
    return list(_plugin_registry.keys())


# Validation decorator for classes
def validate_fields(**validators: Callable[[Any], bool]) -> Callable[[T], T]:
    """Add field validation to a class.

    Args:
        **validators: Field name to validator function mapping
    """

    def decorator(cls: T) -> T:
        original_init = cls.__init__

        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            for field_name, validator in validators.items():
                value = getattr(self, field_name, None)
                if not validator(value):
                    raise ValueError(
                        f"Validation failed for {field_name}: {value!r}"
                    )

        cls.__init__ = new_init  # type: ignore
        return cls

    return decorator


# Usage examples
@singleton
class Configuration:
    """Application configuration (only one instance)."""

    def __init__(self) -> None:
        self.debug = False
        self.api_key = "default"


@auto_repr
class Point:
    """A 2D point with auto-generated __repr__."""

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


@register_plugin("json")
class JSONSerializer:
    """JSON serialization plugin."""

    def serialize(self, data: Any) -> str:
        import json

        return json.dumps(data)


@register_plugin("csv")
class CSVSerializer:
    """CSV serialization plugin."""

    def serialize(self, data: list[dict]) -> str:
        if not data:
            return ""
        headers = data[0].keys()
        lines = [",".join(headers)]
        for row in data:
            lines.append(",".join(str(row.get(h, "")) for h in headers))
        return "\n".join(lines)


@validate_fields(
    name=lambda x: isinstance(x, str) and len(x) > 0,
    age=lambda x: isinstance(x, int) and 0 <= x <= 150,
)
class Person:
    """Person with validated fields."""

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age


if __name__ == "__main__":
    # Test singleton
    config1 = Configuration()
    config1.debug = True
    config2 = Configuration()
    print(f"Same instance: {config1 is config2}")
    print(f"Config debug: {config2.debug}")

    print()

    # Test auto_repr
    point = Point(3.0, 4.0)
    print(f"Point: {point}")

    print()

    # Test plugin registry
    print(f"Available plugins: {list_plugins()}")
    serializer_cls = get_plugin("json")
    if serializer_cls:
        serializer = serializer_cls()
        print(f"JSON: {serializer.serialize({'key': 'value'})}")

    print()

    # Test validation
    person = Person("Alice", 30)
    print(f"Created: {person.name}, {person.age}")

    try:
        Person("", 30)  # Invalid name
    except ValueError as e:
        print(f"Validation error: {e}")
```

**Key points**:
- Class decorators receive the class and return a (possibly modified) class
- Registry pattern is useful for plugins and extensibility
- Singleton pattern ensures only one instance exists

---

### Example 4: Stacking and Composition

**Use case**: Combine multiple decorators effectively.

```python
#!/usr/bin/env python3
"""Stacking decorators and decorator composition."""

import functools
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def log_entry_exit(func: Callable[..., T]) -> Callable[..., T]:
    """Log function entry and exit."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        print(f"→ Entering {func.__name__}")
        try:
            result = func(*args, **kwargs)
            print(f"← Exiting {func.__name__} (success)")
            return result
        except Exception as e:
            print(f"← Exiting {func.__name__} (error: {e})")
            raise

    return wrapper


def timer(func: Callable[..., T]) -> Callable[..., T]:
    """Time function execution."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"  ⏱ {func.__name__} took {elapsed:.4f}s")
        return result

    return wrapper


def validate_args(*validators: Callable[[Any], bool]) -> Callable:
    """Validate positional arguments."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            for i, (arg, validator) in enumerate(zip(args, validators)):
                if not validator(arg):
                    raise ValueError(f"Argument {i} failed validation: {arg!r}")
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Compose decorators into a single decorator
def compose(*decorators: Callable) -> Callable:
    """Compose multiple decorators into one.

    Usage:
        @compose(timer, log_entry_exit)
        def func(): ...

    Is equivalent to:
        @timer
        @log_entry_exit
        def func(): ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        for dec in reversed(decorators):
            func = dec(func)
        return func

    return decorator


# Create composed decorator
logged_and_timed = compose(log_entry_exit, timer)


# Stacked decorators - execution order matters!
@log_entry_exit  # 3rd: Outer wrapper (logs first/last)
@timer  # 2nd: Middle wrapper (times the inner)
@validate_args(lambda x: x > 0, lambda x: x > 0)  # 1st: Inner wrapper
def calculate(a: int, b: int) -> int:
    """Calculate with full instrumentation."""
    time.sleep(0.05)
    return a + b


# Using composed decorator
@logged_and_timed
def process(data: str) -> str:
    """Process data with composed decorator."""
    time.sleep(0.05)
    return data.upper()


# Decorator that preserves other decorators' metadata
def debug(func: Callable[..., T]) -> Callable[..., T]:
    """Add debug capability while preserving all metadata."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # Access original function through wrapper chain
        print(f"DEBUG: Calling {func.__name__}")
        print(f"DEBUG: Args: {args}, Kwargs: {kwargs}")
        result = func(*args, **kwargs)
        print(f"DEBUG: Result: {result}")
        return result

    # Preserve any custom attributes from the wrapped function
    for attr in dir(func):
        if not attr.startswith("_"):
            try:
                setattr(wrapper, attr, getattr(func, attr))
            except AttributeError:
                pass

    return wrapper


if __name__ == "__main__":
    print("=== Stacked Decorators ===")
    result = calculate(5, 3)
    print(f"Result: {result}")

    print()

    print("=== Validation Failure ===")
    try:
        calculate(-1, 3)
    except ValueError as e:
        print(f"Error: {e}")

    print()

    print("=== Composed Decorator ===")
    result = process("hello")
    print(f"Result: {result}")
```

**Key points**:
- Decorators stack bottom-to-top (innermost applied first)
- `compose()` combines decorators for reuse
- Order matters: validation should be innermost, logging outermost

---

## Common Patterns

### Pattern: Memoization (functools.lru_cache)
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
```

### Pattern: Property with Lazy Loading
```python
def lazy_property(func):
    attr_name = f"_lazy_{func.__name__}"

    @property
    @functools.wraps(func)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)

    return wrapper
```

### Pattern: Method Decorator with Self Access
```python
def require_auth(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.is_authenticated:
            raise PermissionError("Authentication required")
        return func(self, *args, **kwargs)
    return wrapper
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Missing @functools.wraps loses metadata
def bad_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@bad_decorator
def my_func():
    """Important docstring."""
    pass

print(my_func.__name__)  # Prints 'wrapper', not 'my_func'!
```

**Do this instead:**
```python
import functools

def good_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

---

**Don't do this:**
```python
# Mutable default argument in decorator
def bad_cache(func):
    cache = {}  # This is fine
    def wrapper(*args, cache={}):  # This is NOT - shared across calls
        ...
```

**Do this instead:**
```python
def good_cache(func):
    cache = {}  # Closure variable - correct
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return wrapper
```

---

## See Also

- [context-managers.md](context-managers.md) - Context manager decorators
- [async-programming.md](async-programming.md) - Async decorators
- [pytest-essentials.md](../testing/pytest-essentials.md) - pytest fixtures as decorators
