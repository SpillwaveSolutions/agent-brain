# Context Managers

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Class-Based Context Managers](#example-1-class-based-context-managers)
  - [Example 2: Generator-Based with contextlib](#example-2-generator-based-with-contextlib)
  - [Example 3: Async Context Managers](#example-3-async-context-managers)
  - [Example 4: Combining Context Managers](#example-4-combining-context-managers)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Pattern | Code |
|---------|------|
| Basic usage | `with open(path) as f: ...` |
| Multiple managers | `with open(a) as f1, open(b) as f2: ...` |
| contextmanager decorator | `@contextlib.contextmanager` |
| Async context manager | `async with aiohttp.ClientSession() as s: ...` |
| Suppress exceptions | `with contextlib.suppress(FileNotFoundError): ...` |
| Redirect stdout | `with contextlib.redirect_stdout(f): ...` |
| Nested managers | `with ExitStack() as stack: ...` |

---

## Core Concepts

Context managers handle resource acquisition and cleanup automatically:

- **`__enter__`**: Called when entering `with` block, returns resource
- **`__exit__`**: Called when exiting, handles cleanup and exceptions
- **`@contextmanager`**: Decorator to create context managers from generators
- **Exception Handling**: `__exit__` receives exception info, can suppress

Context managers ensure cleanup happens even if exceptions occur, making them essential for:
- File handles
- Database connections
- Locks and synchronization
- Temporary state changes

---

## Production Examples

### Example 1: Class-Based Context Managers

**Use case**: Create reusable resource managers with full control.

```python
#!/usr/bin/env python3
"""Class-based context managers for resource management."""

import time
from typing import Any, Self


class Timer:
    """Context manager to time code blocks.

    Usage:
        with Timer("operation") as t:
            do_work()
        print(f"Took {t.elapsed:.2f}s")
    """

    def __init__(self, name: str = "Timer") -> None:
        self.name = name
        self.start_time: float = 0
        self.end_time: float = 0
        self.elapsed: float = 0

    def __enter__(self) -> Self:
        """Start timing when entering context."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Stop timing and optionally log."""
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time
        print(f"{self.name}: {self.elapsed:.4f} seconds")
        # Return False to propagate exceptions
        return False


class DatabaseConnection:
    """Context manager for database connections with transaction support.

    Automatically commits on success, rolls back on exception.
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self.connection: Any = None
        self.cursor: Any = None

    def __enter__(self) -> "DatabaseConnection":
        """Open connection and start transaction."""
        print(f"Connecting to {self.connection_string}")
        # In real code: self.connection = psycopg2.connect(...)
        self.connection = MockConnection()
        self.cursor = self.connection.cursor()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Commit or rollback based on exception status."""
        if exc_type is not None:
            print(f"Rolling back due to {exc_type.__name__}: {exc_val}")
            self.connection.rollback()
        else:
            print("Committing transaction")
            self.connection.commit()

        self.cursor.close()
        self.connection.close()
        print("Connection closed")

        # Don't suppress exceptions
        return False

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query."""
        return self.cursor.execute(query, params)


class MockConnection:
    """Mock database connection for demonstration."""

    def cursor(self) -> "MockCursor":
        return MockCursor()

    def commit(self) -> None:
        print("  [DB] Committed")

    def rollback(self) -> None:
        print("  [DB] Rolled back")

    def close(self) -> None:
        print("  [DB] Connection closed")


class MockCursor:
    """Mock cursor for demonstration."""

    def execute(self, query: str, params: tuple = ()) -> None:
        print(f"  [DB] Executing: {query} with {params}")

    def close(self) -> None:
        print("  [DB] Cursor closed")


class TemporaryDirectory:
    """Create a temporary directory that's cleaned up on exit."""

    def __init__(self, prefix: str = "tmp_") -> None:
        self.prefix = prefix
        self.path: str = ""

    def __enter__(self) -> str:
        """Create temp directory and return path."""
        import tempfile

        self.path = tempfile.mkdtemp(prefix=self.prefix)
        print(f"Created temp dir: {self.path}")
        return self.path

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Remove temp directory and all contents."""
        import shutil

        if self.path:
            shutil.rmtree(self.path, ignore_errors=True)
            print(f"Removed temp dir: {self.path}")
        return False


if __name__ == "__main__":
    # Timer example
    print("=== Timer ===")
    with Timer("sleep operation"):
        time.sleep(0.1)

    print()

    # Database example - success
    print("=== Database (success) ===")
    with DatabaseConnection("postgresql://localhost/test") as db:
        db.execute("INSERT INTO users VALUES (%s, %s)", (1, "Alice"))

    print()

    # Database example - failure
    print("=== Database (failure) ===")
    try:
        with DatabaseConnection("postgresql://localhost/test") as db:
            db.execute("INSERT INTO users VALUES (%s, %s)", (2, "Bob"))
            raise ValueError("Simulated error")
    except ValueError:
        print("Caught the error after cleanup")

    print()

    # Temp directory example
    print("=== Temporary Directory ===")
    with TemporaryDirectory(prefix="myapp_") as tmpdir:
        print(f"Working in: {tmpdir}")
```

**Key points**:
- `__enter__` returns the resource (often `self`)
- `__exit__` receives exception info (or `None` values if no exception)
- Return `True` from `__exit__` to suppress exceptions (rarely needed)
- Always clean up in `__exit__`, even on exception

---

### Example 2: Generator-Based with contextlib

**Use case**: Create simple context managers using generators.

```python
#!/usr/bin/env python3
"""Generator-based context managers with @contextmanager."""

import os
import sys
from contextlib import contextmanager
from io import StringIO
from typing import Generator, Any


@contextmanager
def timer(name: str = "Block") -> Generator[None, None, None]:
    """Time a code block using generator syntax.

    The @contextmanager decorator converts a generator into
    a context manager. Code before yield runs on __enter__,
    code after yield runs on __exit__.
    """
    import time

    start = time.perf_counter()
    try:
        yield  # Control returns to the with block here
    finally:
        elapsed = time.perf_counter() - start
        print(f"{name}: {elapsed:.4f} seconds")


@contextmanager
def working_directory(path: str) -> Generator[str, None, None]:
    """Temporarily change working directory.

    Returns to original directory even if exception occurs.
    """
    original = os.getcwd()
    try:
        os.chdir(path)
        yield path
    finally:
        os.chdir(original)


@contextmanager
def capture_output() -> Generator[StringIO, None, None]:
    """Capture stdout to a StringIO buffer."""
    old_stdout = sys.stdout
    buffer = StringIO()
    try:
        sys.stdout = buffer
        yield buffer
    finally:
        sys.stdout = old_stdout


@contextmanager
def environment_variable(name: str, value: str) -> Generator[None, None, None]:
    """Temporarily set an environment variable."""
    old_value = os.environ.get(name)
    try:
        os.environ[name] = value
        yield
    finally:
        if old_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old_value


@contextmanager
def open_or_stdout(path: str | None) -> Generator[Any, None, None]:
    """Open file for writing, or use stdout if path is None."""
    if path is None:
        yield sys.stdout
    else:
        f = open(path, "w")
        try:
            yield f
        finally:
            f.close()


@contextmanager
def transaction(conn: Any) -> Generator[Any, None, None]:
    """Database transaction with automatic commit/rollback."""
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


@contextmanager
def exception_handler(
    *exceptions: type[Exception],
    default: Any = None,
    log: bool = True,
) -> Generator[list, None, None]:
    """Handle exceptions gracefully with optional logging.

    Usage:
        with exception_handler(ValueError, KeyError, default=0) as result:
            result.append(risky_operation())
        value = result[0] if result else default
    """
    result: list[Any] = []
    try:
        yield result
    except exceptions as e:
        if log:
            print(f"Handled {type(e).__name__}: {e}")
        result.clear()
        result.append(default)


if __name__ == "__main__":
    # Timer
    print("=== Timer ===")
    with timer("computation"):
        total = sum(range(1000000))
    print(f"Result: {total}")

    print()

    # Capture output
    print("=== Capture Output ===")
    with capture_output() as output:
        print("This goes to buffer")
        print("So does this")
    captured = output.getvalue()
    print(f"Captured: {captured!r}")

    print()

    # Environment variable
    print("=== Environment Variable ===")
    print(f"Before: DEBUG={os.environ.get('DEBUG', 'not set')}")
    with environment_variable("DEBUG", "true"):
        print(f"Inside: DEBUG={os.environ.get('DEBUG')}")
    print(f"After: DEBUG={os.environ.get('DEBUG', 'not set')}")

    print()

    # Exception handler
    print("=== Exception Handler ===")
    with exception_handler(ValueError, default=-1) as result:
        result.append(int("not a number"))
    print(f"Result: {result[0]}")
```

**Key points**:
- `@contextmanager` converts generators to context managers
- Code before `yield` = `__enter__`, code after = `__exit__`
- Use `try/finally` to ensure cleanup happens
- `yield` value becomes available in `with ... as var`

---

### Example 3: Async Context Managers

**Use case**: Manage async resources like HTTP sessions and database pools.

```python
#!/usr/bin/env python3
"""Async context managers for async resource management."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any


class AsyncDatabasePool:
    """Async database connection pool."""

    def __init__(self, url: str, min_size: int = 5, max_size: int = 20) -> None:
        self.url = url
        self.min_size = min_size
        self.max_size = max_size
        self._pool: Any = None

    async def __aenter__(self) -> "AsyncDatabasePool":
        """Create the connection pool."""
        print(f"Creating pool for {self.url}")
        await asyncio.sleep(0.1)  # Simulate connection time
        self._pool = "mock_pool"
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Close all connections in the pool."""
        print("Closing connection pool")
        await asyncio.sleep(0.05)  # Simulate cleanup
        self._pool = None
        return False

    async def acquire(self) -> "AsyncConnection":
        """Get a connection from the pool."""
        return AsyncConnection()


class AsyncConnection:
    """Async database connection."""

    async def execute(self, query: str) -> list[dict[str, Any]]:
        """Execute a query."""
        await asyncio.sleep(0.01)  # Simulate query
        return [{"id": 1, "name": "Alice"}]

    async def close(self) -> None:
        """Return connection to pool."""
        await asyncio.sleep(0.01)


@asynccontextmanager
async def async_timer(name: str = "Block") -> AsyncGenerator[None, None]:
    """Async timer using @asynccontextmanager."""
    import time

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{name}: {elapsed:.4f} seconds")


@asynccontextmanager
async def http_session() -> AsyncGenerator[Any, None]:
    """Manage aiohttp ClientSession lifecycle."""
    # In real code: session = aiohttp.ClientSession()
    session = MockAsyncSession()
    try:
        yield session
    finally:
        await session.close()


class MockAsyncSession:
    """Mock async HTTP session."""

    async def get(self, url: str) -> dict[str, Any]:
        await asyncio.sleep(0.01)
        return {"status": 200, "url": url}

    async def close(self) -> None:
        print("Session closed")


@asynccontextmanager
async def async_lock_with_timeout(
    lock: asyncio.Lock,
    timeout: float,
) -> AsyncGenerator[None, None]:
    """Acquire lock with timeout."""
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
        yield
    finally:
        lock.release()


@asynccontextmanager
async def managed_task(
    coro: Any,
    name: str = "task",
) -> AsyncGenerator[asyncio.Task, None]:
    """Create and manage an async task with cleanup."""
    task = asyncio.create_task(coro, name=name)
    try:
        yield task
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                print(f"Task {name} cancelled")


async def main() -> None:
    """Demonstrate async context managers."""
    # Async database pool
    print("=== Async Database Pool ===")
    async with AsyncDatabasePool("postgres://localhost/db") as pool:
        conn = await pool.acquire()
        results = await conn.execute("SELECT * FROM users")
        print(f"Query results: {results}")

    print()

    # Async timer
    print("=== Async Timer ===")
    async with async_timer("async work"):
        await asyncio.sleep(0.1)

    print()

    # HTTP session
    print("=== HTTP Session ===")
    async with http_session() as session:
        response = await session.get("https://api.example.com")
        print(f"Response: {response}")

    print()

    # Managed task
    print("=== Managed Task ===")

    async def background_work() -> None:
        while True:
            print("Working...")
            await asyncio.sleep(0.5)

    async with managed_task(background_work(), name="worker") as task:
        await asyncio.sleep(0.3)
        print("Exiting context, task will be cancelled")


if __name__ == "__main__":
    asyncio.run(main())
```

**Key points**:
- Use `async with` for async context managers
- `__aenter__` and `__aexit__` are async methods
- `@asynccontextmanager` for generator-based async managers
- Essential for aiohttp sessions, database pools, etc.

---

### Example 4: Combining Context Managers

**Use case**: Manage multiple resources with ExitStack.

```python
#!/usr/bin/env python3
"""Combining and nesting context managers with ExitStack."""

from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from typing import Generator, Any
import tempfile


@contextmanager
def named_temp_file(name: str) -> Generator[Path, None, None]:
    """Create a named temp file."""
    import os

    fd, path = tempfile.mkstemp(prefix=name)
    try:
        os.close(fd)
        yield Path(path)
    finally:
        Path(path).unlink(missing_ok=True)


def process_files(paths: list[Path]) -> list[str]:
    """Process multiple files, ensuring all are closed properly.

    ExitStack manages multiple context managers dynamically.
    """
    results = []

    with ExitStack() as stack:
        # Open all files - they'll all be closed on exit
        files = [stack.enter_context(open(p)) for p in paths]

        for f in files:
            results.append(f.read())

    return results


def dynamic_context_management() -> None:
    """Demonstrate dynamic context manager registration."""
    with ExitStack() as stack:
        # Register cleanup callbacks
        stack.callback(print, "Cleanup 1")
        stack.callback(print, "Cleanup 2")

        # Conditionally enter context managers
        should_log = True
        if should_log:

            @contextmanager
            def logging_context() -> Generator[None, None, None]:
                print("Logging started")
                yield
                print("Logging stopped")

            stack.enter_context(logging_context())

        print("Doing work...")

    # Cleanup runs in reverse order: Cleanup 2, Cleanup 1


def transfer_cleanup() -> tuple[list[Path], ExitStack]:
    """Transfer cleanup responsibility using pop_all().

    Useful when setup succeeds and caller takes ownership.
    """
    stack = ExitStack()
    temp_files: list[Path] = []

    try:
        # Create resources
        for i in range(3):
            path = Path(stack.enter_context(named_temp_file(f"file{i}_")))
            temp_files.append(path)

        # Success! Transfer cleanup to caller
        return temp_files, stack.pop_all()

    except Exception:
        # Failure - ExitStack cleans up automatically
        raise


def nested_contexts() -> None:
    """Multiple context managers in one with statement."""
    # Modern syntax (Python 3.10+)
    with (
        open("/dev/null", "w") as f1,
        open("/dev/null", "w") as f2,
        suppress(FileNotFoundError),
    ):
        f1.write("test")
        f2.write("test")

    # Pre-3.10 syntax
    with ExitStack() as stack:
        f1 = stack.enter_context(open("/dev/null", "w"))
        f2 = stack.enter_context(open("/dev/null", "w"))
        stack.enter_context(suppress(FileNotFoundError))
        f1.write("test")
        f2.write("test")


def push_context_manager() -> None:
    """Manually push context managers onto ExitStack."""
    with ExitStack() as stack:
        # Push using the push() method
        @contextmanager
        def resource() -> Generator[str, None, None]:
            print("Resource acquired")
            yield "resource"
            print("Resource released")

        cm = resource()
        value = stack.enter_context(cm)
        print(f"Got: {value}")


if __name__ == "__main__":
    print("=== Dynamic Context Management ===")
    dynamic_context_management()

    print()

    print("=== Transfer Cleanup ===")
    files, cleanup_stack = transfer_cleanup()
    print(f"Created files: {[str(f) for f in files]}")
    # Caller is responsible for cleanup
    cleanup_stack.close()
    print("Caller cleaned up")

    print()

    print("=== Push Context Manager ===")
    push_context_manager()
```

**Key points**:
- `ExitStack` manages multiple context managers dynamically
- `stack.callback()` registers cleanup functions
- `stack.pop_all()` transfers cleanup responsibility
- Cleanup happens in reverse order of registration

---

## Common Patterns

### Pattern: Reentrant Context Manager
```python
import threading

class ReentrantLock:
    def __init__(self):
        self._lock = threading.RLock()

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *args):
        self._lock.release()
        return False
```

### Pattern: Optional Context Manager
```python
from contextlib import nullcontext

def process(data, lock=None):
    cm = lock if lock else nullcontext()
    with cm:
        # Process data
        pass
```

### Pattern: Context Manager as Decorator
```python
from contextlib import ContextDecorator

class log_calls(ContextDecorator):
    def __enter__(self):
        print("Entering")
        return self

    def __exit__(self, *args):
        print("Exiting")
        return False

@log_calls()
def my_function():
    print("Working")
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Suppressing all exceptions silently
class BadManager:
    def __exit__(self, *args):
        return True  # Suppresses ALL exceptions!
```

**Do this instead:**
```python
class GoodManager:
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only suppress specific, expected exceptions
        if exc_type is ExpectedError:
            log.warning(f"Suppressed: {exc_val}")
            return True
        return False  # Propagate unexpected exceptions
```

---

**Don't do this:**
```python
# Missing cleanup in generator context manager
@contextmanager
def bad_resource():
    resource = acquire()
    yield resource
    release(resource)  # Never runs if exception!
```

**Do this instead:**
```python
@contextmanager
def good_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)  # Always runs
```

---

## See Also

- [async-programming.md](async-programming.md) - Async context managers
- [decorators.md](decorators.md) - Context managers as decorators
- [error-handling.md](error-handling.md) - Exception handling in context managers
