# Type Hints and Static Analysis

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Basic Type Annotations](#example-1-basic-type-annotations)
  - [Example 2: Generic Types with Python 3.12+](#example-2-generic-types-with-python-312)
  - [Example 3: Protocols for Structural Typing](#example-3-protocols-for-structural-typing)
  - [Example 4: Pydantic Runtime Validation](#example-4-pydantic-runtime-validation)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Pattern | Code |
|---------|------|
| Basic annotation | `def greet(name: str) -> str:` |
| Optional type | `title: str \| None = None` |
| List of strings | `names: list[str] = []` |
| Dict type | `scores: dict[str, int] = {}` |
| Union type | `value: int \| str` |
| Type alias | `type Point = tuple[float, float]` |
| Generic class | `class Box[T]: ...` |

---

## Core Concepts

Type hints provide optional static typing while maintaining Python's dynamic nature. They enable:
- **Early error detection** via tools like mypy and pyright
- **Better IDE support** with intelligent autocompletion
- **Self-documenting code** that clarifies function contracts

Python 3.9+ allows built-in types as generics (`list[str]` instead of `List[str]`).
Python 3.10+ introduced the `|` operator for unions (`int | None` instead of `Optional[int]`).
Python 3.12+ adds type parameter syntax for generics and the `type` statement for aliases.

---

## Production Examples

### Example 1: Basic Type Annotations

**Use case**: Annotate variables, functions, and classes for clarity and validation.

```python
#!/usr/bin/env python3
"""Basic type annotation patterns for Python 3.12+."""

from typing import Optional

# Variable annotations
count: int = 0
name: str = "Alice"
is_active: bool = True
temperature: float = 98.6

# Function with full type annotations
def calculate_average(numbers: list[float]) -> float:
    """Calculate the average of a list of numbers.

    Args:
        numbers: List of numeric values

    Returns:
        The arithmetic mean of the input values
    """
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


# Function with optional parameter
def greet(name: str, title: str | None = None) -> str:
    """Generate a greeting message.

    Args:
        name: The person's name
        title: Optional title (Mr., Ms., Dr., etc.)

    Returns:
        Formatted greeting string
    """
    if title is not None:
        return f"Hello, {title} {name}!"
    return f"Hello, {name}!"


# Class with type annotations
class User:
    """Represents a system user with typed attributes."""

    default_role: str = "guest"  # Class variable

    def __init__(self, name: str, age: int) -> None:
        self.name: str = name
        self.age: int = age
        self.active: bool = True

    def deactivate(self) -> None:
        """Mark the user as inactive."""
        self.active = False


if __name__ == "__main__":
    # Usage examples
    avg = calculate_average([1.0, 2.0, 3.0, 4.0, 5.0])
    print(f"Average: {avg}")

    print(greet("Alice"))
    print(greet("Smith", "Dr."))

    user = User("Bob", 30)
    print(f"User: {user.name}, Active: {user.active}")
```

**Key points**:
- Use lowercase built-in types: `list`, `dict`, `tuple`, `set`
- Use `|` for union types instead of `Union[]`
- Return `None` explicitly for functions that return nothing

---

### Example 2: Generic Types with Python 3.12+

**Use case**: Create reusable, type-safe containers and functions.

```python
#!/usr/bin/env python3
"""Generic types with Python 3.12+ type parameter syntax."""

from typing import TypeAlias

# Python 3.12+ type alias declaration
type Point = tuple[float, float]
type UserData = dict[str, str | int | bool]
type Matrix = list[list[float]]


# Python 3.12+ generic class syntax
class Box[T]:
    """A generic container that holds a single value.

    Type Parameters:
        T: The type of value this box contains
    """

    def __init__(self, content: T) -> None:
        self._content = content

    def get(self) -> T:
        """Retrieve the contained value."""
        return self._content

    def set(self, value: T) -> None:
        """Replace the contained value."""
        self._content = value


# Generic function with type parameter
def first[T](items: list[T]) -> T | None:
    """Return the first item from a list, or None if empty.

    Type Parameters:
        T: The type of items in the list

    Args:
        items: A list of items

    Returns:
        The first item, or None if the list is empty
    """
    return items[0] if items else None


# Multiple type parameters
class Pair[K, V]:
    """A generic key-value pair container.

    Type Parameters:
        K: The type of the key
        V: The type of the value
    """

    def __init__(self, key: K, value: V) -> None:
        self.key = key
        self.value = value

    def swap(self) -> "Pair[V, K]":
        """Create a new Pair with key and value swapped."""
        return Pair(self.value, self.key)


if __name__ == "__main__":
    # Using Box with different types
    int_box: Box[int] = Box(42)
    str_box: Box[str] = Box("hello")

    print(f"Int box: {int_box.get()}")
    print(f"Str box: {str_box.get()}")

    # Using generic function
    numbers = [1, 2, 3]
    names = ["Alice", "Bob"]

    print(f"First number: {first(numbers)}")
    print(f"First name: {first(names)}")

    # Using Pair
    pair: Pair[str, int] = Pair("age", 30)
    swapped = pair.swap()
    print(f"Original: {pair.key}={pair.value}")
    print(f"Swapped: {swapped.key}={swapped.value}")
```

**Key points**:
- Python 3.12 `class Box[T]:` syntax replaces `class Box(Generic[T]):`
- `type` statement creates explicit type aliases
- Generic functions use `def func[T](...)` syntax

---

### Example 3: Protocols for Structural Typing

**Use case**: Define interfaces based on behavior (duck typing) for flexible design.

```python
#!/usr/bin/env python3
"""Protocols enable structural typing - interfaces based on behavior."""

from typing import Protocol, runtime_checkable


class Greeter(Protocol):
    """Protocol defining objects that can greet.

    Any class implementing a `greet(name: str) -> str` method
    satisfies this protocol without explicit inheritance.
    """

    def greet(self, name: str) -> str:
        """Generate a greeting for the given name."""
        ...


class Closeable(Protocol):
    """Protocol for resources that can be closed."""

    def close(self) -> None:
        """Release resources."""
        ...


@runtime_checkable
class Sized(Protocol):
    """Protocol for objects with a length.

    The @runtime_checkable decorator enables isinstance() checks.
    """

    def __len__(self) -> int:
        ...


# Implementations don't need to inherit from protocols
class FriendlyGreeter:
    """A friendly greeter implementation."""

    def greet(self, name: str) -> str:
        return f"Hello, {name}! Nice to meet you!"


class FormalGreeter:
    """A formal greeter implementation."""

    def __init__(self, title: str = "Dear") -> None:
        self.title = title

    def greet(self, name: str) -> str:
        return f"{self.title} {name}, greetings."


# Function accepting any Greeter
def welcome(greeter: Greeter, name: str) -> str:
    """Welcome someone using any greeter implementation.

    Args:
        greeter: Any object with a greet() method
        name: The person to welcome

    Returns:
        The greeting message
    """
    return greeter.greet(name)


# Database-like example with Closeable
class DatabaseConnection:
    """Simulated database connection."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._open = True
        print(f"Connected to {url}")

    def close(self) -> None:
        self._open = False
        print(f"Disconnected from {self.url}")


def use_resource(resource: Closeable) -> None:
    """Use and close any closeable resource."""
    try:
        print("Using resource...")
    finally:
        resource.close()


if __name__ == "__main__":
    # Different greeters work with the same function
    friendly = FriendlyGreeter()
    formal = FormalGreeter("Esteemed")

    print(welcome(friendly, "Alice"))
    print(welcome(formal, "Bob"))

    # Closeable protocol
    db = DatabaseConnection("postgres://localhost/mydb")
    use_resource(db)

    # Runtime checking with @runtime_checkable
    print(f"\nIs [1,2,3] Sized? {isinstance([1, 2, 3], Sized)}")
    print(f"Is 42 Sized? {isinstance(42, Sized)}")
```

**Key points**:
- Protocols define structural interfaces without inheritance
- Classes satisfy protocols implicitly by implementing required methods
- `@runtime_checkable` enables `isinstance()` checks (use sparingly)

---

### Example 4: Pydantic Runtime Validation

**Use case**: Validate data at runtime using type hints with Pydantic.

```python
#!/usr/bin/env python3
"""Pydantic v2 for runtime type validation and settings management."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings


class User(BaseModel):
    """User model with automatic validation.

    Pydantic validates types at runtime and converts compatible values.
    """

    id: int
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    age: int = Field(..., ge=0, le=150)
    balance: Decimal = Field(default=Decimal("0.00"))

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Ensure name is not just whitespace."""
        if not v.strip():
            raise ValueError("name cannot be empty or whitespace")
        return v.strip()


class Order(BaseModel):
    """Order with nested validation and custom validators."""

    order_id: str
    user_id: int
    items: list[str] = Field(..., min_length=1)
    total: Decimal = Field(..., gt=0)
    created_at: date = Field(default_factory=date.today)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "order_id": "ORD-001",
                    "user_id": 1,
                    "items": ["Widget", "Gadget"],
                    "total": "99.99",
                }
            ]
        }
    }

    @model_validator(mode="after")
    def validate_order(self) -> "Order":
        """Validate order-level constraints."""
        if len(self.items) > 100:
            raise ValueError("Cannot have more than 100 items per order")
        return self


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables.

    Pydantic Settings automatically reads from environment variables
    and .env files, with type conversion and validation.
    """

    # Database settings
    database_url: str = "sqlite:///./app.db"
    database_pool_size: int = Field(default=5, ge=1, le=100)

    # API settings
    api_key: SecretStr  # Hides value in logs/repr
    debug: bool = False
    log_level: str = Field(default="INFO")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "APP_",  # APP_DATABASE_URL, APP_API_KEY, etc.
    }


if __name__ == "__main__":
    # Valid user creation
    user = User(
        id=1,
        name="Alice Smith",
        email="alice@example.com",
        age=30,
    )
    print(f"User: {user.model_dump_json(indent=2)}")

    # Type coercion - string "42" becomes int 42
    user2 = User(
        id="42",  # type: ignore - Pydantic converts this
        name="Bob",
        email="bob@example.com",
        age="25",  # type: ignore - Also converted
    )
    print(f"User2 ID type: {type(user2.id)}")  # <class 'int'>

    # Validation error example
    try:
        invalid_user = User(
            id=1,
            name="",
            email="invalid-email",
            age=200,
        )
    except Exception as e:
        print(f"\nValidation error: {e}")

    # Order with nested validation
    order = Order(
        order_id="ORD-001",
        user_id=1,
        items=["Laptop", "Mouse"],
        total=Decimal("1299.99"),
    )
    print(f"\nOrder: {order.model_dump_json(indent=2)}")
```

**Key points**:
- Pydantic validates and coerces types at runtime
- Use `Field()` for constraints like `min_length`, `ge`, `pattern`
- `SecretStr` hides sensitive values from logs
- `BaseSettings` loads config from environment variables automatically

---

## Common Patterns

### Pattern: Function Overloads
```python
from typing import overload

@overload
def process(value: str) -> str: ...
@overload
def process(value: int) -> int: ...

def process(value: str | int) -> str | int:
    if isinstance(value, str):
        return value.upper()
    return value * 2
```

### Pattern: TypedDict for JSON-like Data
```python
from typing import TypedDict, Required, NotRequired

class UserDict(TypedDict):
    id: Required[int]
    name: Required[str]
    email: NotRequired[str]

user: UserDict = {"id": 1, "name": "Alice"}
```

### Pattern: Callable Types
```python
from collections.abc import Callable

def apply_twice(func: Callable[[int], int], value: int) -> int:
    return func(func(value))

result = apply_twice(lambda x: x * 2, 5)  # 20
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Using Any defeats the purpose of type hints
from typing import Any

def process(data: Any) -> Any:
    return data.do_something()
```

**Do this instead:**
```python
# Use specific types or protocols
from typing import Protocol

class Processable(Protocol):
    def do_something(self) -> str: ...

def process(data: Processable) -> str:
    return data.do_something()
```

---

**Don't do this:**
```python
# Mutable default arguments with type hints
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items
```

**Do this instead:**
```python
# Use None and create new list in function body
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

---

## See Also

- [pydantic-validation.md](../web-apis/pydantic-validation.md) - Deep dive into Pydantic models
- [error-handling.md](../patterns/error-handling.md) - Typing exception handling
- [pytest-essentials.md](../testing/pytest-essentials.md) - Type hints in tests
