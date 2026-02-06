# Asynchronous Programming and Concurrency

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: TaskGroup for Structured Concurrency](#example-1-taskgroup-for-structured-concurrency)
  - [Example 2: Timeout Handling](#example-2-timeout-handling)
  - [Example 3: Async HTTP Client with Retry](#example-3-async-http-client-with-retry)
  - [Example 4: Thread Pool for Blocking I/O](#example-4-thread-pool-for-blocking-io)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Run async function | `asyncio.run(main())` |
| Create task | `task = asyncio.create_task(coro())` |
| Wait with timeout | `async with asyncio.timeout(5): ...` |
| TaskGroup | `async with asyncio.TaskGroup() as tg: tg.create_task(...)` |
| Gather results | `results = await asyncio.gather(*coros)` |
| Run in thread | `await asyncio.to_thread(blocking_func)` |
| Sleep | `await asyncio.sleep(1.0)` |
| Semaphore limit | `async with asyncio.Semaphore(10): ...` |

---

## Core Concepts

Asyncio enables concurrent I/O-bound operations without threads. Key concepts:

- **Coroutines**: Functions defined with `async def` that can be paused and resumed
- **Event Loop**: Manages and schedules coroutine execution
- **Tasks**: Wrap coroutines for concurrent execution
- **Structured Concurrency**: Python 3.11+ `TaskGroup` ensures all tasks complete or fail together

Python 3.11+ introduced significant improvements:
- `asyncio.TaskGroup` for structured concurrency
- `asyncio.timeout()` context manager
- Exception groups (`except*`) for handling multiple exceptions

---

## Production Examples

### Example 1: TaskGroup for Structured Concurrency

**Use case**: Fetch multiple URLs concurrently with proper error handling.

```python
#!/usr/bin/env python3
"""Structured concurrency with TaskGroup (Python 3.11+)."""

import asyncio
from dataclasses import dataclass


@dataclass
class FetchResult:
    """Result from fetching a URL."""

    url: str
    status: int
    content_length: int


async def fetch_url(url: str) -> FetchResult:
    """Simulate fetching a URL."""
    # Simulate network delay
    await asyncio.sleep(0.1)

    # Simulate occasional failures
    if "error" in url:
        raise ValueError(f"Failed to fetch {url}")

    return FetchResult(url=url, status=200, content_length=1024)


async def fetch_all(urls: list[str]) -> list[FetchResult]:
    """Fetch all URLs concurrently using TaskGroup.

    TaskGroup ensures:
    - All tasks complete before exiting the context
    - If any task fails, all others are cancelled
    - All exceptions are collected into an ExceptionGroup
    """
    results: list[FetchResult] = []

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_url(url)) for url in urls]

    # All tasks completed successfully if we reach here
    results = [task.result() for task in tasks]
    return results


async def fetch_with_error_handling(urls: list[str]) -> list[FetchResult | None]:
    """Fetch URLs with individual error handling."""
    results: list[FetchResult | None] = []

    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(fetch_url(url)) for url in urls]
    except* ValueError as exc_group:
        # Handle ValueError exceptions from failed fetches
        for exc in exc_group.exceptions:
            print(f"Fetch error: {exc}")
        # Return results for tasks that succeeded
        results = [
            task.result() if not task.cancelled() and task.exception() is None else None
            for task in tasks
        ]
    else:
        results = [task.result() for task in tasks]

    return results


if __name__ == "__main__":
    urls = [
        "https://example.com/api/1",
        "https://example.com/api/2",
        "https://example.com/api/3",
    ]

    # Successful fetch
    results = asyncio.run(fetch_all(urls))
    for r in results:
        print(f"Fetched {r.url}: {r.status}")

    # With error handling
    urls_with_error = urls + ["https://example.com/error"]
    results = asyncio.run(fetch_with_error_handling(urls_with_error))
    print(f"Got {len([r for r in results if r])} successful results")
```

**Key points**:
- `TaskGroup` replaces manual `gather()` with exception handling
- Use `except*` to catch specific exceptions from the group
- All tasks are automatically cancelled if one fails (unless handled)

---

### Example 2: Timeout Handling

**Use case**: Set timeouts for async operations to prevent hanging.

```python
#!/usr/bin/env python3
"""Timeout handling with asyncio.timeout() (Python 3.11+)."""

import asyncio
from contextlib import suppress


async def slow_operation(duration: float) -> str:
    """Simulate a slow operation."""
    await asyncio.sleep(duration)
    return f"Completed after {duration}s"


async def fetch_with_timeout(timeout_seconds: float) -> str | None:
    """Fetch with a timeout, returning None on timeout."""
    try:
        async with asyncio.timeout(timeout_seconds):
            result = await slow_operation(2.0)
            return result
    except TimeoutError:
        print(f"Operation timed out after {timeout_seconds}s")
        return None


async def fetch_with_deadline() -> str | None:
    """Use timeout_at for absolute deadline."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 1.0  # 1 second from now

    try:
        async with asyncio.timeout_at(deadline):
            return await slow_operation(2.0)
    except TimeoutError:
        return None


async def multiple_with_individual_timeouts() -> list[str | None]:
    """Each task gets its own timeout."""
    async def fetch_one(url: str, timeout: float) -> str | None:
        try:
            async with asyncio.timeout(timeout):
                await asyncio.sleep(0.5)  # Simulate fetch
                return f"Fetched {url}"
        except TimeoutError:
            return None

    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(fetch_one("url1", 1.0)),
            tg.create_task(fetch_one("url2", 0.3)),  # Will timeout
            tg.create_task(fetch_one("url3", 1.0)),
        ]

    return [t.result() for t in tasks]


async def reschedule_timeout() -> str:
    """Dynamically extend timeout based on progress."""
    async with asyncio.timeout(1.0) as cm:
        await asyncio.sleep(0.5)

        # Reschedule to give more time
        cm.reschedule(asyncio.get_running_loop().time() + 2.0)

        await asyncio.sleep(1.0)  # Would have timed out without reschedule
        return "Completed with extended timeout"


if __name__ == "__main__":
    # Basic timeout
    result = asyncio.run(fetch_with_timeout(1.0))
    print(f"Result: {result}")

    # Reschedule example
    result = asyncio.run(reschedule_timeout())
    print(f"Reschedule result: {result}")
```

**Key points**:
- `asyncio.timeout(seconds)` replaces `asyncio.wait_for()`
- `timeout_at()` uses absolute timestamps for deadlines
- `cm.reschedule()` can extend timeouts dynamically

---

### Example 3: Async HTTP Client with Retry

**Use case**: Production HTTP client with retry logic and connection pooling.

```python
#!/usr/bin/env python3
"""Async HTTP client with retry and connection management."""

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


@dataclass
class APIResponse:
    """Structured API response."""

    status: int
    data: dict[str, Any]
    elapsed_ms: float


class AsyncAPIClient:
    """Production async HTTP client with retry and pooling."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_connections: int = 100,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=20,
            ttl_dns_cache=300,
        )
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "AsyncAPIClient":
        """Create session on context entry."""
        self._session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close session on context exit."""
        if self._session:
            await self._session.close()
            self._session = None

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get(self, path: str) -> APIResponse:
        """GET request with automatic retry."""
        if not self._session:
            raise RuntimeError("Client not initialized. Use async with.")

        url = f"{self.base_url}/{path.lstrip('/')}"

        async with self._session.get(url) as response:
            data = await response.json()
            return APIResponse(
                status=response.status,
                data=data,
                elapsed_ms=0.0,  # Would calculate from start time
            )

    async def get_many(
        self,
        paths: list[str],
        concurrency: int = 10,
    ) -> list[APIResponse | Exception]:
        """Fetch multiple paths with limited concurrency."""
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_one(path: str) -> APIResponse | Exception:
            async with semaphore:
                try:
                    return await self.get(path)
                except Exception as e:
                    return e

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(fetch_one(p)) for p in paths]

        return [t.result() for t in tasks]


async def main() -> None:
    """Demonstrate async HTTP client usage."""
    async with AsyncAPIClient("https://api.example.com") as client:
        # Single request
        response = await client.get("/users/1")
        print(f"Status: {response.status}")

        # Multiple concurrent requests
        paths = [f"/users/{i}" for i in range(1, 11)]
        results = await client.get_many(paths, concurrency=5)
        successes = [r for r in results if isinstance(r, APIResponse)]
        print(f"Fetched {len(successes)} users")


if __name__ == "__main__":
    asyncio.run(main())
```

**Key points**:
- Use `aiohttp.TCPConnector` for connection pooling
- `Semaphore` limits concurrent requests
- `tenacity` provides declarative retry logic

---

### Example 4: Thread Pool for Blocking I/O

**Use case**: Run blocking operations without blocking the event loop.

```python
#!/usr/bin/env python3
"""Mixing async with blocking I/O using thread pools."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def blocking_file_read(path: Path) -> str:
    """Blocking file operation (runs in thread pool)."""
    time.sleep(0.1)  # Simulate slow I/O
    return path.read_text() if path.exists() else ""


def cpu_intensive_task(data: str) -> int:
    """CPU-bound task (runs in thread pool)."""
    # Simulate CPU work
    total = sum(ord(c) for c in data)
    return total


async def process_files(paths: list[Path]) -> list[int]:
    """Process files using thread pool for blocking operations."""
    loop = asyncio.get_running_loop()
    results: list[int] = []

    # Create a dedicated thread pool
    with ThreadPoolExecutor(max_workers=4) as pool:
        # Read all files concurrently in threads
        read_tasks = [
            loop.run_in_executor(pool, blocking_file_read, path)
            for path in paths
        ]
        contents = await asyncio.gather(*read_tasks)

        # Process contents in threads
        process_tasks = [
            loop.run_in_executor(pool, cpu_intensive_task, content)
            for content in contents
        ]
        results = await asyncio.gather(*process_tasks)

    return results


async def simple_blocking_call() -> str:
    """Use asyncio.to_thread for simple blocking calls."""
    # Python 3.9+ convenience function
    result = await asyncio.to_thread(blocking_file_read, Path("test.txt"))
    return result


async def mixed_async_and_sync() -> None:
    """Combine async and sync operations."""
    # Async operation
    await asyncio.sleep(0.1)

    # Blocking operation in thread
    data = await asyncio.to_thread(time.sleep, 0.1)

    # More async operations
    async with asyncio.TaskGroup() as tg:
        tg.create_task(asyncio.sleep(0.1))
        tg.create_task(asyncio.to_thread(time.sleep, 0.1))


if __name__ == "__main__":
    # Process multiple files
    paths = [Path(f"file_{i}.txt") for i in range(5)]
    results = asyncio.run(process_files(paths))
    print(f"Processed {len(results)} files")
```

**Key points**:
- `asyncio.to_thread()` is the simplest way to run blocking code
- `run_in_executor()` allows custom thread/process pools
- Never call blocking code directly in async functions

---

## Common Patterns

### Pattern: Async Context Manager
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_resource():
    resource = await acquire_resource()
    try:
        yield resource
    finally:
        await release_resource(resource)

async def use_resource():
    async with managed_resource() as r:
        await r.do_work()
```

### Pattern: Rate Limiting with Semaphore
```python
async def rate_limited_fetch(urls: list[str], max_concurrent: int = 5):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch(url: str):
        async with semaphore:
            return await do_fetch(url)

    return await asyncio.gather(*[fetch(url) for url in urls])
```

### Pattern: Cancellation Handling
```python
async def cancellable_operation():
    try:
        while True:
            await asyncio.sleep(1)
            # Do work
    except asyncio.CancelledError:
        # Cleanup before propagating
        await cleanup()
        raise
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Blocking the event loop
async def bad_example():
    time.sleep(1)  # Blocks entire event loop!
    data = requests.get(url)  # Also blocking!
```

**Do this instead:**
```python
async def good_example():
    await asyncio.sleep(1)  # Non-blocking
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
```

---

**Don't do this:**
```python
# Fire and forget tasks (may be garbage collected)
async def bad_fire_and_forget():
    asyncio.create_task(some_background_work())
    # Task might be GC'd before completion!
```

**Do this instead:**
```python
# Keep references to background tasks
background_tasks = set()

async def good_fire_and_forget():
    task = asyncio.create_task(some_background_work())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
```

---

## See Also

- [error-handling.md](error-handling.md) - Exception groups and async error handling
- [context-managers.md](context-managers.md) - Async context managers
- [fastapi-patterns.md](../web-apis/fastapi-patterns.md) - Async web frameworks
