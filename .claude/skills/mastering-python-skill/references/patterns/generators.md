# Generators and Iterators

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Basic Generators](#example-1-basic-generators)
  - [Example 2: Generator Pipelines](#example-2-generator-pipelines)
  - [Example 3: Custom Iterators](#example-3-custom-iterators)
  - [Example 4: Generator Expressions and Comprehensions](#example-4-generator-expressions-and-comprehensions)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Pattern | Code |
|---------|------|
| Generator function | `def gen(): yield value` |
| Generator expression | `(x * 2 for x in range(10))` |
| Yield from | `yield from other_generator()` |
| Send to generator | `gen.send(value)` |
| Close generator | `gen.close()` |
| Next value | `next(gen)` or `next(gen, default)` |
| Iterate all | `list(gen)` or `for x in gen: ...` |
| itertools chain | `itertools.chain(iter1, iter2)` |

---

## Core Concepts

Generators provide lazy evaluation - values are computed on demand:

- **Generator Functions**: Use `yield` to produce values one at a time
- **Generator Expressions**: Compact syntax like `(x for x in items)`
- **Lazy Evaluation**: Memory-efficient processing of large datasets
- **Iterator Protocol**: `__iter__` and `__next__` methods

Benefits of generators:
- **Memory Efficiency**: Process one item at a time instead of loading all into memory
- **Pipeline Processing**: Chain operations without intermediate lists
- **Infinite Sequences**: Represent sequences without finite bounds
- **Coroutine Support**: Foundation for async programming

---

## Production Examples

### Example 1: Basic Generators

**Use case**: Create memory-efficient iterators for large datasets.

```python
#!/usr/bin/env python3
"""Basic generator patterns for lazy evaluation."""

from typing import Generator, Iterator


def countdown(n: int) -> Generator[int, None, None]:
    """Generate countdown from n to 1.

    Generators use yield instead of return. Each yield
    produces a value and pauses execution until next() is called.
    """
    while n > 0:
        yield n
        n -= 1


def fibonacci(limit: int | None = None) -> Generator[int, None, None]:
    """Generate Fibonacci numbers up to optional limit.

    Without a limit, this generates an infinite sequence.
    """
    a, b = 0, 1
    while limit is None or a <= limit:
        yield a
        a, b = b, a + b


def read_large_file(path: str) -> Generator[str, None, None]:
    """Read a large file line by line without loading into memory.

    This is the idiomatic way to process large files in Python.
    """
    with open(path, "r") as f:
        for line in f:
            yield line.rstrip("\n")


def chunk_iterator(
    iterable: Iterator,
    chunk_size: int,
) -> Generator[list, None, None]:
    """Split an iterator into chunks of specified size.

    Useful for batch processing without loading all data.
    """
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def take(n: int, iterable: Iterator) -> Generator:
    """Take first n items from any iterator."""
    for i, item in enumerate(iterable):
        if i >= n:
            break
        yield item


def skip(n: int, iterable: Iterator) -> Generator:
    """Skip first n items from any iterator."""
    for i, item in enumerate(iterable):
        if i >= n:
            yield item


if __name__ == "__main__":
    # Basic countdown
    print("=== Countdown ===")
    for n in countdown(5):
        print(n, end=" ")
    print()

    # Fibonacci with limit
    print("\n=== Fibonacci up to 100 ===")
    for fib in fibonacci(100):
        print(fib, end=" ")
    print()

    # Take from infinite sequence
    print("\n=== First 10 Fibonacci ===")
    first_ten = list(take(10, fibonacci()))
    print(first_ten)

    # Chunking
    print("\n=== Chunks of 3 ===")
    data = range(10)
    for chunk in chunk_iterator(iter(data), 3):
        print(chunk)

    # Generator state
    print("\n=== Generator State ===")
    gen = countdown(3)
    print(f"First: {next(gen)}")
    print(f"Second: {next(gen)}")
    print(f"Third: {next(gen)}")
    try:
        next(gen)
    except StopIteration:
        print("Generator exhausted")
```

**Key points**:
- `yield` produces a value and suspends execution
- Generators remember state between `next()` calls
- Use `StopIteration` to signal end of iteration
- Generators are single-use - iterate once only

---

### Example 2: Generator Pipelines

**Use case**: Process data through multiple transformation stages efficiently.

```python
#!/usr/bin/env python3
"""Generator pipelines for streaming data processing."""

import re
from typing import Generator, Iterable


def read_lines(paths: Iterable[str]) -> Generator[str, None, None]:
    """Read lines from multiple files."""
    for path in paths:
        try:
            with open(path) as f:
                for line in f:
                    yield line.rstrip()
        except FileNotFoundError:
            continue


def filter_pattern(
    lines: Iterable[str],
    pattern: str,
) -> Generator[str, None, None]:
    """Filter lines matching a regex pattern."""
    regex = re.compile(pattern)
    for line in lines:
        if regex.search(line):
            yield line


def extract_field(
    lines: Iterable[str],
    delimiter: str,
    field: int,
) -> Generator[str, None, None]:
    """Extract a specific field from delimited lines."""
    for line in lines:
        parts = line.split(delimiter)
        if len(parts) > field:
            yield parts[field]


def parse_int(
    values: Iterable[str],
    default: int = 0,
) -> Generator[int, None, None]:
    """Parse strings to integers with default for failures."""
    for value in values:
        try:
            yield int(value.strip())
        except ValueError:
            yield default


def running_average(
    numbers: Iterable[float],
) -> Generator[float, None, None]:
    """Calculate running average of numbers."""
    total = 0.0
    count = 0
    for num in numbers:
        total += num
        count += 1
        yield total / count


def batch(
    items: Iterable,
    size: int,
) -> Generator[list, None, None]:
    """Batch items into groups."""
    current_batch: list = []
    for item in items:
        current_batch.append(item)
        if len(current_batch) >= size:
            yield current_batch
            current_batch = []
    if current_batch:
        yield current_batch


# Pipeline composition function
def pipeline(*functions):
    """Compose multiple generator functions into a pipeline."""

    def run(data):
        for func in functions:
            data = func(data)
        return data

    return run


# Example: Log analysis pipeline
def analyze_logs(log_files: list[str]) -> dict:
    """Analyze log files using generator pipeline.

    This processes files line by line, never loading
    everything into memory.
    """
    # Simulated log processing pipeline
    lines = [
        "2024-01-15 10:00:00 INFO User login: user_id=123",
        "2024-01-15 10:00:01 ERROR Connection failed: timeout",
        "2024-01-15 10:00:02 INFO User login: user_id=456",
        "2024-01-15 10:00:03 WARN Memory usage high: 85%",
        "2024-01-15 10:00:04 ERROR Connection failed: refused",
        "2024-01-15 10:00:05 INFO User login: user_id=789",
    ]

    # Count errors
    errors = list(filter_pattern(iter(lines), r"ERROR"))

    # Extract user IDs from login lines
    login_lines = filter_pattern(iter(lines), r"User login")
    user_ids = extract_field(login_lines, "=", 1)

    return {
        "error_count": len(errors),
        "errors": errors,
        "user_ids": list(user_ids),
    }


if __name__ == "__main__":
    # Simple pipeline
    print("=== Simple Pipeline ===")
    data = ["1", "2", "3", "4", "5"]
    numbers = parse_int(data)
    doubled = (x * 2 for x in numbers)
    result = list(doubled)
    print(f"Doubled: {result}")

    print()

    # Running average
    print("=== Running Average ===")
    values = [10, 20, 30, 40, 50]
    for avg in running_average(values):
        print(f"Running avg: {avg:.2f}")

    print()

    # Batching
    print("=== Batching ===")
    items = range(10)
    for b in batch(items, 3):
        print(f"Batch: {b}")

    print()

    # Log analysis
    print("=== Log Analysis ===")
    results = analyze_logs([])
    print(f"Errors: {results['error_count']}")
    print(f"User IDs: {results['user_ids']}")
```

**Key points**:
- Chain generators to create processing pipelines
- Data flows through one item at a time
- No intermediate lists needed
- Compose functions for reusable pipelines

---

### Example 3: Custom Iterators

**Use case**: Create iterator classes with full protocol support.

```python
#!/usr/bin/env python3
"""Custom iterator classes implementing the iterator protocol."""

from typing import Iterator, Any, Self


class Range:
    """Custom range implementation showing iterator protocol."""

    def __init__(self, start: int, stop: int | None = None, step: int = 1) -> None:
        if stop is None:
            self.start = 0
            self.stop = start
        else:
            self.start = start
            self.stop = stop
        self.step = step

    def __iter__(self) -> Iterator[int]:
        """Return an iterator object.

        This makes Range iterable (can be used in for loops).
        """
        return RangeIterator(self.start, self.stop, self.step)

    def __len__(self) -> int:
        """Return the number of items."""
        return max(0, (self.stop - self.start + self.step - 1) // self.step)


class RangeIterator:
    """Iterator for Range class."""

    def __init__(self, start: int, stop: int, step: int) -> None:
        self.current = start
        self.stop = stop
        self.step = step

    def __iter__(self) -> Self:
        """Iterators return themselves."""
        return self

    def __next__(self) -> int:
        """Return the next value or raise StopIteration."""
        if (self.step > 0 and self.current >= self.stop) or \
           (self.step < 0 and self.current <= self.stop):
            raise StopIteration
        value = self.current
        self.current += self.step
        return value


class ReusableGenerator:
    """Wrapper to make a generator reusable.

    Normal generators can only be iterated once. This class
    allows multiple iterations by recreating the generator.
    """

    def __init__(self, generator_func: callable, *args: Any, **kwargs: Any) -> None:
        self.generator_func = generator_func
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator:
        """Create a fresh generator each time."""
        return self.generator_func(*self.args, **self.kwargs)


class InfiniteCounter:
    """Infinite iterator that never stops."""

    def __init__(self, start: int = 0, step: int = 1) -> None:
        self.current = start
        self.step = step

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> int:
        value = self.current
        self.current += self.step
        return value


class CycleIterator:
    """Cycle through items indefinitely."""

    def __init__(self, items: list) -> None:
        if not items:
            raise ValueError("Cannot cycle empty list")
        self.items = items
        self.index = 0

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        item = self.items[self.index]
        self.index = (self.index + 1) % len(self.items)
        return item


class LookAheadIterator:
    """Iterator with peek() capability."""

    def __init__(self, iterable: Iterator) -> None:
        self.iterator = iter(iterable)
        self._buffer: list = []

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        if self._buffer:
            return self._buffer.pop(0)
        return next(self.iterator)

    def peek(self, default: Any = None) -> Any:
        """Look at next item without consuming it."""
        if not self._buffer:
            try:
                self._buffer.append(next(self.iterator))
            except StopIteration:
                return default
        return self._buffer[0]

    def has_next(self) -> bool:
        """Check if there are more items."""
        if self._buffer:
            return True
        try:
            self._buffer.append(next(self.iterator))
            return True
        except StopIteration:
            return False


if __name__ == "__main__":
    # Custom Range
    print("=== Custom Range ===")
    r = Range(1, 10, 2)
    print(f"Length: {len(r)}")
    print(f"Values: {list(r)}")
    # Can iterate again
    print(f"Again: {list(r)}")

    print()

    # Reusable generator
    print("=== Reusable Generator ===")

    def squares(n: int):
        for i in range(n):
            yield i * i

    reusable = ReusableGenerator(squares, 5)
    print(f"First: {list(reusable)}")
    print(f"Second: {list(reusable)}")

    print()

    # Infinite counter (take first 5)
    print("=== Infinite Counter ===")
    counter = InfiniteCounter(start=10, step=5)
    first_five = [next(counter) for _ in range(5)]
    print(f"First 5: {first_five}")

    print()

    # Cycle
    print("=== Cycle ===")
    cycle = CycleIterator(["A", "B", "C"])
    cycle_sample = [next(cycle) for _ in range(7)]
    print(f"Cycled: {cycle_sample}")

    print()

    # Look ahead
    print("=== Look Ahead ===")
    lookahead = LookAheadIterator([1, 2, 3])
    print(f"Peek: {lookahead.peek()}")
    print(f"Has next: {lookahead.has_next()}")
    print(f"Next: {next(lookahead)}")
    print(f"Peek: {lookahead.peek()}")
```

**Key points**:
- `__iter__` returns an iterator (often `self` or a dedicated iterator object)
- `__next__` returns the next value or raises `StopIteration`
- Separate iterable and iterator for multiple iterations
- Custom iterators enable peek, rewind, or other features

---

### Example 4: Generator Expressions and Comprehensions

**Use case**: Write concise, memory-efficient data transformations.

```python
#!/usr/bin/env python3
"""Generator expressions and comprehensions for concise code."""

from typing import Any


def comprehension_examples() -> None:
    """Demonstrate all comprehension types."""
    data = range(10)

    # List comprehension - creates a list
    squares_list = [x**2 for x in data]
    print(f"List: {squares_list}")

    # Generator expression - lazy, memory efficient
    squares_gen = (x**2 for x in data)
    print(f"Generator: {squares_gen}")  # Shows generator object
    print(f"As list: {list(squares_gen)}")

    # Dict comprehension
    square_dict = {x: x**2 for x in data}
    print(f"Dict: {square_dict}")

    # Set comprehension
    squares_set = {x**2 for x in data}
    print(f"Set: {squares_set}")


def filtering_examples() -> None:
    """Demonstrate filtering in comprehensions."""
    numbers = range(20)

    # Filter with condition
    evens = [x for x in numbers if x % 2 == 0]
    print(f"Evens: {evens}")

    # Multiple conditions
    div_by_2_and_3 = [x for x in numbers if x % 2 == 0 if x % 3 == 0]
    print(f"Divisible by 2 and 3: {div_by_2_and_3}")

    # Conditional expression (ternary)
    labels = ["even" if x % 2 == 0 else "odd" for x in range(5)]
    print(f"Labels: {labels}")


def nested_examples() -> None:
    """Demonstrate nested comprehensions."""
    # Flatten 2D list
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    flat = [x for row in matrix for x in row]
    print(f"Flattened: {flat}")

    # Cartesian product
    colors = ["red", "blue"]
    sizes = ["S", "M", "L"]
    combinations = [(c, s) for c in colors for s in sizes]
    print(f"Combinations: {combinations}")

    # Nested with condition
    filtered = [x for row in matrix for x in row if x % 2 == 0]
    print(f"Even numbers: {filtered}")

    # Create 2D structure
    multiplication_table = [[i * j for j in range(1, 6)] for i in range(1, 6)]
    print("Multiplication table:")
    for row in multiplication_table:
        print(row)


def memory_comparison() -> None:
    """Show memory difference between list and generator."""
    import sys

    n = 1000000

    # List uses significant memory
    list_data = [x**2 for x in range(n)]
    print(f"List size: {sys.getsizeof(list_data):,} bytes")

    # Generator uses minimal memory
    gen_data = (x**2 for x in range(n))
    print(f"Generator size: {sys.getsizeof(gen_data):,} bytes")

    # But generator can only be consumed once!
    del list_data, gen_data


def practical_examples() -> None:
    """Practical uses of comprehensions."""
    # Parse CSV-like data
    raw_data = ["Alice,30,Engineer", "Bob,25,Designer", "Carol,35,Manager"]

    # Parse to dict
    people = [
        {"name": p[0], "age": int(p[1]), "role": p[2]}
        for line in raw_data
        for p in [line.split(",")]  # Unpack in nested comprehension
    ]
    print(f"People: {people}")

    # Index lookup dict
    name_to_age = {p["name"]: p["age"] for p in people}
    print(f"Name to age: {name_to_age}")

    # Filter and transform
    seniors = {p["name"]: p["role"] for p in people if p["age"] >= 30}
    print(f"Seniors: {seniors}")

    # File processing with generator
    def process_config(lines: list[str]) -> dict[str, str]:
        """Parse key=value config lines."""
        return {
            k: v
            for line in lines
            if "=" in line and not line.strip().startswith("#")
            for k, v in [line.strip().split("=", 1)]
        }

    config_lines = [
        "# This is a comment",
        "host=localhost",
        "port=8080",
        "debug=true",
    ]
    config = process_config(config_lines)
    print(f"Config: {config}")


def generator_function_vs_expression() -> None:
    """Compare generator function and expression."""
    # Generator expression - simple transformations
    squares = (x**2 for x in range(10))

    # Generator function - complex logic
    def complex_squares(n: int):
        """Generator function allows complex logic."""
        for x in range(n):
            if x % 2 == 0:
                yield x**2
            else:
                yield x**3

    print(f"Expression: {list(squares)}")
    print(f"Function: {list(complex_squares(10))}")


if __name__ == "__main__":
    print("=== Comprehension Types ===")
    comprehension_examples()

    print("\n=== Filtering ===")
    filtering_examples()

    print("\n=== Nested ===")
    nested_examples()

    print("\n=== Memory Comparison ===")
    memory_comparison()

    print("\n=== Practical Examples ===")
    practical_examples()

    print("\n=== Function vs Expression ===")
    generator_function_vs_expression()
```

**Key points**:
- Generator expressions use `()`, list comprehensions use `[]`
- Generator expressions are lazy and memory-efficient
- Use comprehensions for clear, single-expression transformations
- Use generator functions for complex logic

---

## Common Patterns

### Pattern: yield from for Delegation
```python
def chain(*iterables):
    """Flatten multiple iterables."""
    for it in iterables:
        yield from it  # Delegate to sub-iterator

result = list(chain([1, 2], [3, 4], [5]))  # [1, 2, 3, 4, 5]
```

### Pattern: Two-Way Generator (Coroutine)
```python
def accumulator():
    """Generator that receives values via send()."""
    total = 0
    while True:
        value = yield total
        if value is not None:
            total += value

acc = accumulator()
next(acc)  # Prime the generator
acc.send(10)  # Returns 10
acc.send(20)  # Returns 30
```

### Pattern: itertools Utilities
```python
import itertools

# Chain iterables
itertools.chain([1, 2], [3, 4])

# Repeat value
itertools.repeat("x", 3)  # x, x, x

# Cycle through
itertools.cycle([1, 2, 3])  # 1, 2, 3, 1, 2, 3, ...

# Combinations
itertools.combinations([1, 2, 3], 2)  # (1,2), (1,3), (2,3)
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Iterating an exhausted generator
gen = (x for x in range(5))
print(list(gen))  # [0, 1, 2, 3, 4]
print(list(gen))  # [] - Empty! Generator is exhausted
```

**Do this instead:**
```python
# Create fresh generator each time
def make_gen():
    return (x for x in range(5))

print(list(make_gen()))  # [0, 1, 2, 3, 4]
print(list(make_gen()))  # [0, 1, 2, 3, 4]
```

---

**Don't do this:**
```python
# Loading everything into memory defeats the purpose
data = list(huge_generator())  # Loads all into memory!
for item in data:
    process(item)
```

**Do this instead:**
```python
# Process one at a time
for item in huge_generator():  # Never loads all into memory
    process(item)
```

---

## See Also

- [async-programming.md](async-programming.md) - Async generators
- [context-managers.md](context-managers.md) - Generator-based context managers
- [decorators.md](decorators.md) - Decorator patterns with generators
