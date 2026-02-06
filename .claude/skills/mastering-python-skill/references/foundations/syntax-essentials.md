# Python Syntax Essentials

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Modern String Formatting](#example-1-modern-string-formatting)
  - [Example 2: Comprehensions and Generators](#example-2-comprehensions-and-generators)
  - [Example 3: Structural Pattern Matching](#example-3-structural-pattern-matching)
  - [Example 4: Walrus Operator and Modern Syntax](#example-4-walrus-operator-and-modern-syntax)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Pattern | Code |
|---------|------|
| f-string | `f"Hello, {name}!"` |
| f-string debug | `f"{value=}"` → `value=42` |
| List comprehension | `[x*2 for x in items if x > 0]` |
| Dict comprehension | `{k: v for k, v in pairs}` |
| Walrus operator | `if (n := len(items)) > 10:` |
| Match statement | `match value: case 1: ...` |
| Unpacking | `first, *rest, last = items` |
| Merge dicts | `merged = {**dict1, **dict2}` |

---

## Core Concepts

Modern Python (3.10+) provides expressive syntax for common operations:
- **f-strings** for readable string interpolation with expressions
- **Comprehensions** for creating collections declaratively
- **Pattern matching** (3.10+) for structural decomposition
- **Walrus operator** (3.8+) for assignment expressions

Python emphasizes readability and explicit over implicit behavior. The Zen of Python (`import this`) guides idiomatic code: prefer flat over nested, simple over complex.

---

## Production Examples

### Example 1: Modern String Formatting

**Use case**: Format strings clearly and safely in production code.

```python
#!/usr/bin/env python3
"""Modern string formatting with f-strings."""

from datetime import datetime
from decimal import Decimal


def format_examples() -> None:
    """Demonstrate f-string capabilities."""
    name = "Alice"
    age = 30
    balance = Decimal("1234.56")
    items = ["apple", "banana", "cherry"]

    # Basic interpolation
    print(f"Name: {name}, Age: {age}")

    # Expression evaluation
    print(f"Age in months: {age * 12}")

    # Method calls
    print(f"Uppercase: {name.upper()}")

    # Debug mode (Python 3.8+) - prints variable name and value
    print(f"{name=}, {age=}")
    # Output: name='Alice', age=30

    # Formatting specifications
    print(f"Balance: ${balance:,.2f}")  # $1,234.56
    print(f"Percentage: {0.856:.1%}")   # 85.6%
    print(f"Padded: {age:05d}")         # 00030
    print(f"Left align: {name:<10}|")   # Alice     |
    print(f"Center: {name:^10}|")       # Alice  |

    # Date formatting
    now = datetime.now()
    print(f"Date: {now:%Y-%m-%d %H:%M}")

    # Conditional expressions
    status = "adult" if age >= 18 else "minor"
    print(f"Status: {status}")

    # Multi-line f-strings
    report = f"""
    User Report
    -----------
    Name:    {name}
    Age:     {age}
    Balance: ${balance:,.2f}
    Items:   {len(items)}
    """
    print(report)


def format_numbers() -> None:
    """Number formatting patterns."""
    value = 1234567.89

    # Thousands separator
    print(f"Comma: {value:,.2f}")       # 1,234,567.89
    print(f"Underscore: {value:_.2f}")  # 1_234_567.89

    # Scientific notation
    print(f"Scientific: {value:.2e}")   # 1.23e+06

    # Binary, octal, hex
    n = 255
    print(f"Binary: {n:b}")   # 11111111
    print(f"Octal: {n:o}")    # 377
    print(f"Hex: {n:x}")      # ff
    print(f"Hex upper: {n:X}")  # FF


def safe_string_formatting(user_input: str) -> str:
    """Safely format strings with user input.

    Never use .format() or % with untrusted input!
    f-strings are safer because expressions are evaluated
    at definition time, not runtime.
    """
    # Safe: f-string with escaped output
    return f"User said: {user_input!r}"


if __name__ == "__main__":
    format_examples()
    format_numbers()
    print(safe_string_formatting("Hello\nWorld"))
```

**Key points**:
- Use `{var=}` for debug output showing name and value
- Use format specs like `:,.2f` for numbers
- f-strings are evaluated at definition, safer than `.format()`

---

### Example 2: Comprehensions and Generators

**Use case**: Create collections and iterators declaratively.

```python
#!/usr/bin/env python3
"""Comprehensions and generators for declarative data transformation."""

from collections.abc import Generator, Iterator
from typing import Any


def list_comprehensions() -> None:
    """List comprehension patterns."""
    numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    # Basic transformation
    doubled = [x * 2 for x in numbers]
    print(f"Doubled: {doubled}")

    # With filter
    evens = [x for x in numbers if x % 2 == 0]
    print(f"Evens: {evens}")

    # Combined transformation and filter
    doubled_evens = [x * 2 for x in numbers if x % 2 == 0]
    print(f"Doubled evens: {doubled_evens}")

    # Nested loops (flatten)
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    flat = [x for row in matrix for x in row]
    print(f"Flattened: {flat}")

    # Conditional expression in output
    labels = ["even" if x % 2 == 0 else "odd" for x in numbers[:5]]
    print(f"Labels: {labels}")


def dict_comprehensions() -> None:
    """Dictionary comprehension patterns."""
    words = ["apple", "banana", "cherry"]

    # Create dict from list
    word_lengths = {word: len(word) for word in words}
    print(f"Lengths: {word_lengths}")

    # Filter and transform
    items = {"a": 1, "b": 2, "c": 3, "d": 4}
    filtered = {k: v * 10 for k, v in items.items() if v > 1}
    print(f"Filtered: {filtered}")

    # Swap keys and values
    swapped = {v: k for k, v in items.items()}
    print(f"Swapped: {swapped}")

    # From two lists with zip
    keys = ["name", "age", "city"]
    values = ["Alice", 30, "NYC"]
    combined = dict(zip(keys, values))
    print(f"Combined: {combined}")


def set_comprehensions() -> None:
    """Set comprehension patterns."""
    words = ["hello", "world", "hello", "python"]

    # Unique first letters
    first_letters = {word[0] for word in words}
    print(f"First letters: {first_letters}")

    # Unique lengths
    lengths = {len(word) for word in words}
    print(f"Unique lengths: {lengths}")


def generator_expressions() -> None:
    """Generator expressions for memory efficiency."""
    # Generator expression (lazy evaluation)
    squares_gen = (x**2 for x in range(1000000))
    print(f"Generator: {squares_gen}")
    print(f"First 5: {[next(squares_gen) for _ in range(5)]}")

    # Sum without creating intermediate list
    total = sum(x**2 for x in range(1000))
    print(f"Sum of squares: {total}")

    # any() and all() with generators
    numbers = [2, 4, 6, 8, 10]
    all_even = all(x % 2 == 0 for x in numbers)
    any_greater = any(x > 5 for x in numbers)
    print(f"All even: {all_even}, Any > 5: {any_greater}")


def generator_function() -> Generator[int, None, None]:
    """Generator function with yield.

    Yields:
        Fibonacci numbers indefinitely
    """
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def take(n: int, iterable: Iterator[Any]) -> list[Any]:
    """Take first n items from an iterator."""
    return [next(iterable) for _ in range(n)]


def pipeline_example() -> None:
    """Demonstrate generator pipelines."""

    def numbers() -> Generator[int, None, None]:
        """Generate numbers 1 to infinity."""
        n = 1
        while True:
            yield n
            n += 1

    def square(nums: Iterator[int]) -> Generator[int, None, None]:
        """Square each number."""
        for n in nums:
            yield n ** 2

    def filter_even(nums: Iterator[int]) -> Generator[int, None, None]:
        """Keep only even numbers."""
        for n in nums:
            if n % 2 == 0:
                yield n

    # Compose pipeline (lazy - nothing computed yet)
    pipeline = filter_even(square(numbers()))

    # Only computes what's needed
    result = take(5, pipeline)
    print(f"Pipeline result: {result}")  # [4, 16, 36, 64, 100]


if __name__ == "__main__":
    list_comprehensions()
    print()
    dict_comprehensions()
    print()
    set_comprehensions()
    print()
    generator_expressions()
    print()
    fib = generator_function()
    print(f"First 10 Fibonacci: {take(10, fib)}")
    print()
    pipeline_example()
```

**Key points**:
- Use list comprehensions for small-to-medium transformations
- Use generators for large data or infinite sequences
- Generators enable memory-efficient pipelines
- Prefer `sum(x for x in ...)` over `sum([x for x in ...])`

---

### Example 3: Structural Pattern Matching

**Use case**: Match and destructure complex data structures (Python 3.10+).

```python
#!/usr/bin/env python3
"""Structural pattern matching (Python 3.10+)."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Point:
    """A 2D point."""
    x: float
    y: float


@dataclass
class Circle:
    """A circle shape."""
    center: Point
    radius: float


@dataclass
class Rectangle:
    """A rectangle shape."""
    top_left: Point
    width: float
    height: float


def describe_point(point: Point) -> str:
    """Describe a point's location using pattern matching."""
    match point:
        case Point(x=0, y=0):
            return "Origin"
        case Point(x=0, y=y):
            return f"On Y-axis at y={y}"
        case Point(x=x, y=0):
            return f"On X-axis at x={x}"
        case Point(x=x, y=y) if x == y:
            return f"On diagonal at ({x}, {y})"
        case Point(x=x, y=y):
            return f"Point at ({x}, {y})"


def calculate_area(shape: Circle | Rectangle) -> float:
    """Calculate area using pattern matching on types."""
    import math

    match shape:
        case Circle(radius=r):
            return math.pi * r ** 2
        case Rectangle(width=w, height=h):
            return w * h
        case _:
            raise ValueError(f"Unknown shape: {shape}")


def process_command(command: dict[str, Any]) -> str:
    """Process commands using pattern matching on dict structure."""
    match command:
        case {"action": "quit"}:
            return "Goodbye!"
        case {"action": "greet", "name": name}:
            return f"Hello, {name}!"
        case {"action": "add", "x": x, "y": y}:
            return f"Result: {x + y}"
        case {"action": "list", "items": [first, *rest]}:
            return f"First: {first}, remaining: {len(rest)}"
        case {"action": action}:
            return f"Unknown action: {action}"
        case _:
            return "Invalid command"


def process_http_response(response: tuple[int, str]) -> str:
    """Match HTTP response codes."""
    match response:
        case (200, body):
            return f"Success: {body[:50]}..."
        case (201, _):
            return "Created"
        case (204, _):
            return "No content"
        case (301 | 302, _):
            return "Redirect"
        case (400, _):
            return "Bad request"
        case (401 | 403, _):
            return "Auth error"
        case (404, _):
            return "Not found"
        case (status, _) if 500 <= status < 600:
            return f"Server error: {status}"
        case (status, _):
            return f"Unknown status: {status}"


def parse_json_event(event: dict[str, Any]) -> str:
    """Parse JSON events with nested patterns."""
    match event:
        case {
            "type": "user",
            "action": "login",
            "data": {"user_id": uid, "timestamp": ts}
        }:
            return f"User {uid} logged in at {ts}"

        case {
            "type": "order",
            "action": "created",
            "data": {"order_id": oid, "items": [_, *_] as items}
        }:
            return f"Order {oid} created with {len(items)} items"

        case {"type": t, "action": a}:
            return f"Event: {t}/{a}"

        case _:
            return "Unknown event format"


if __name__ == "__main__":
    # Point matching
    points = [
        Point(0, 0),
        Point(0, 5),
        Point(3, 0),
        Point(4, 4),
        Point(3, 7),
    ]
    for p in points:
        print(f"{p} -> {describe_point(p)}")

    print()

    # Shape matching
    shapes = [
        Circle(Point(0, 0), 5),
        Rectangle(Point(0, 0), 4, 3),
    ]
    for shape in shapes:
        print(f"{shape} -> area = {calculate_area(shape):.2f}")

    print()

    # Command matching
    commands = [
        {"action": "greet", "name": "Alice"},
        {"action": "add", "x": 5, "y": 3},
        {"action": "list", "items": [1, 2, 3, 4]},
        {"action": "unknown"},
    ]
    for cmd in commands:
        print(f"{cmd} -> {process_command(cmd)}")

    print()

    # HTTP response matching
    responses = [
        (200, "OK data"),
        (404, "Not found"),
        (500, "Error"),
    ]
    for resp in responses:
        print(f"{resp[0]} -> {process_http_response(resp)}")
```

**Key points**:
- Pattern matching replaces complex if/elif chains
- Use `|` for OR patterns, guards for conditions
- Capture values with variable names in patterns
- `_` matches anything without binding

---

### Example 4: Walrus Operator and Modern Syntax

**Use case**: Write concise code with assignment expressions and modern features.

```python
#!/usr/bin/env python3
"""Modern Python syntax features (3.8+)."""

import re
from pathlib import Path


def walrus_examples() -> None:
    """Walrus operator (:=) for assignment expressions."""

    # Read and check in one expression
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    # Without walrus: need separate lines
    # n = len(data)
    # if n > 5:
    #     print(f"Long list: {n} items")

    # With walrus: combine assignment and condition
    if (n := len(data)) > 5:
        print(f"Long list: {n} items")

    # In list comprehensions
    results = [y for x in data if (y := x ** 2) > 10]
    print(f"Squares > 10: {results}")

    # In while loops
    lines = ["line 1", "line 2", "line 3", ""]
    index = 0
    while (line := lines[index] if index < len(lines) else ""):
        print(f"Processing: {line}")
        index += 1

    # With regex
    text = "Contact: alice@example.com or bob@test.org"
    pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    if match := re.search(pattern, text):
        print(f"Found email: {match.group()}")

    # Find all with any()
    numbers = [1, 3, 5, 8, 9]
    if any((even := n) % 2 == 0 for n in numbers):
        print(f"First even: {even}")


def unpacking_examples() -> None:
    """Extended unpacking with * operator."""

    # Basic unpacking
    first, second, third = [1, 2, 3]

    # Capture rest with *
    first, *middle, last = [1, 2, 3, 4, 5]
    print(f"First: {first}, Middle: {middle}, Last: {last}")
    # First: 1, Middle: [2, 3, 4], Last: 5

    # Head and tail
    head, *tail = [1, 2, 3, 4]
    print(f"Head: {head}, Tail: {tail}")

    # Ignore values with _
    name, _, age = ("Alice", "ignored", 30)

    # Nested unpacking
    data = [("Alice", 30), ("Bob", 25)]
    for name, age in data:
        print(f"{name} is {age}")

    # Dict merging (3.9+)
    defaults = {"color": "red", "size": "medium"}
    overrides = {"size": "large", "quantity": 5}
    merged = {**defaults, **overrides}
    print(f"Merged: {merged}")

    # Dict union operator (3.9+)
    merged2 = defaults | overrides
    print(f"Union: {merged2}")


def positional_only_params(x: int, y: int, /, *, keyword: str) -> str:
    """Function with positional-only and keyword-only params.

    Args:
        x: First positional-only parameter
        y: Second positional-only parameter
        keyword: Keyword-only parameter

    The / marks end of positional-only params.
    The * marks start of keyword-only params.
    """
    return f"x={x}, y={y}, keyword={keyword}"


def modern_file_handling() -> None:
    """Modern file handling with pathlib and walrus."""
    from tempfile import NamedTemporaryFile

    # Create temp file for demo
    with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Line 1\nLine 2\nLine 3\n")
        temp_path = Path(f.name)

    # Read with walrus for EOF check
    with open(temp_path) as f:
        while line := f.readline():
            print(f"Read: {line.strip()}")

    # Pathlib operations
    if temp_path.exists():
        print(f"File size: {temp_path.stat().st_size} bytes")
        print(f"Suffix: {temp_path.suffix}")
        temp_path.unlink()  # Delete


def exception_groups() -> None:
    """Exception groups (Python 3.11+)."""

    def process_items(items: list[str]) -> list[str]:
        """Process items, collecting all errors."""
        results = []
        errors = []

        for item in items:
            try:
                if item.startswith("bad"):
                    raise ValueError(f"Invalid item: {item}")
                results.append(item.upper())
            except ValueError as e:
                errors.append(e)

        if errors:
            raise ExceptionGroup("Processing errors", errors)

        return results

    try:
        process_items(["good", "bad1", "ok", "bad2"])
    except* ValueError as eg:
        print(f"Caught {len(eg.exceptions)} ValueError(s)")
        for e in eg.exceptions:
            print(f"  - {e}")


if __name__ == "__main__":
    print("=== Walrus Operator ===")
    walrus_examples()

    print("\n=== Unpacking ===")
    unpacking_examples()

    print("\n=== Positional-Only Params ===")
    result = positional_only_params(1, 2, keyword="test")
    print(result)

    print("\n=== File Handling ===")
    modern_file_handling()

    print("\n=== Exception Groups ===")
    exception_groups()
```

**Key points**:
- Walrus operator (`:=`) enables inline assignment
- Use `/` for positional-only, `*` for keyword-only params
- Extended unpacking with `*rest` captures remaining items
- Dict union `|` merges dicts (3.9+)

---

## Common Patterns

### Pattern: Guard Clauses
```python
def process(data: list[int] | None) -> int:
    # Early return for edge cases
    if data is None:
        return 0
    if not data:
        return 0
    if len(data) == 1:
        return data[0]

    # Main logic after guards
    return sum(data) // len(data)
```

### Pattern: EAFP (Easier to Ask Forgiveness)
```python
# Pythonic: try/except (EAFP)
try:
    value = my_dict["key"]
except KeyError:
    value = "default"

# Also good: .get() for dicts
value = my_dict.get("key", "default")
```

### Pattern: Context Variables
```python
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("request_id", default="unknown")

def log(message: str) -> None:
    print(f"[{request_id.get()}] {message}")
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Mutable default argument (shared between calls!)
def append_to(item, target=[]):
    target.append(item)
    return target
```

**Do this instead:**
```python
def append_to(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target
```

---

**Don't do this:**
```python
# Using type() for type checking
if type(x) == list:
    ...
```

**Do this instead:**
```python
# Use isinstance for proper type checking
if isinstance(x, list):
    ...
# Or for ABCs
from collections.abc import Sequence
if isinstance(x, Sequence):
    ...
```

---

## See Also

- [type-systems.md](type-systems.md) - Type hints and annotations
- [generators.md](../patterns/generators.md) - Generator patterns in depth
- [error-handling.md](../patterns/error-handling.md) - Exception handling
