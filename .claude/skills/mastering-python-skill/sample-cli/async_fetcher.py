#!/usr/bin/env python3
"""
Async HTTP Fetcher CLI

Demonstrates async/await patterns for HTTP requests:
- Concurrent fetching with asyncio.gather()
- Rate limiting with semaphores
- Timeout handling
- Structured error handling

Usage:
    python async_fetcher.py https://api.github.com
    python async_fetcher.py --concurrency 3 url1 url2 url3 url4
    python async_fetcher.py --timeout 5.0 https://httpbin.org/delay/3

See: ../references/patterns/async-programming.md
"""

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Any

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class FetchResult:
    """Result of a URL fetch operation."""

    url: str
    status_code: int | None
    content_length: int
    elapsed_ms: float
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.status_code is not None

    def __str__(self) -> str:
        if self.success:
            return (
                f"[OK] {self.url}\n"
                f"     Status: {self.status_code}, "
                f"Size: {self.content_length:,} bytes, "
                f"Time: {self.elapsed_ms:.0f}ms"
            )
        return f"[ERROR] {self.url}\n     {self.error}"


# ============================================================
# ASYNC FETCHER
# ============================================================

class AsyncFetcher:
    """Async HTTP client with rate limiting and timeout support."""

    def __init__(
        self,
        max_concurrency: int = 5,
        timeout: float = 10.0,
        user_agent: str = "AsyncFetcher/1.0",
    ):
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self.user_agent = user_agent
        self._semaphore: asyncio.Semaphore | None = None

    async def fetch_one(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> FetchResult:
        """Fetch a single URL with rate limiting."""
        # Acquire semaphore for rate limiting
        assert self._semaphore is not None

        async with self._semaphore:
            start_time = time.perf_counter()

            try:
                response = await client.get(
                    url,
                    timeout=self.timeout,
                    follow_redirects=True,
                )

                elapsed_ms = (time.perf_counter() - start_time) * 1000

                return FetchResult(
                    url=url,
                    status_code=response.status_code,
                    content_length=len(response.content),
                    elapsed_ms=elapsed_ms,
                )

            except httpx.TimeoutException:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return FetchResult(
                    url=url,
                    status_code=None,
                    content_length=0,
                    elapsed_ms=elapsed_ms,
                    error=f"Timeout after {self.timeout}s",
                )

            except httpx.ConnectError as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return FetchResult(
                    url=url,
                    status_code=None,
                    content_length=0,
                    elapsed_ms=elapsed_ms,
                    error=f"Connection error: {e}",
                )

            except httpx.HTTPError as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return FetchResult(
                    url=url,
                    status_code=None,
                    content_length=0,
                    elapsed_ms=elapsed_ms,
                    error=f"HTTP error: {e}",
                )

    async def fetch_all(self, urls: list[str]) -> list[FetchResult]:
        """Fetch multiple URLs concurrently with rate limiting."""
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            http2=True,
        ) as client:
            # Create tasks for all URLs
            tasks = [self.fetch_one(client, url) for url in urls]

            # Execute concurrently with gather
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any unexpected exceptions
            processed_results: list[FetchResult] = []
            for url, result in zip(urls, results):
                if isinstance(result, Exception):
                    processed_results.append(
                        FetchResult(
                            url=url,
                            status_code=None,
                            content_length=0,
                            elapsed_ms=0,
                            error=str(result),
                        )
                    )
                else:
                    processed_results.append(result)

            return processed_results


# ============================================================
# CLI
# ============================================================

def print_summary(results: list[FetchResult], total_time: float) -> None:
    """Print summary statistics."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total URLs:     {len(results)}")
    print(f"Successful:     {len(successful)}")
    print(f"Failed:         {len(failed)}")
    print(f"Total time:     {total_time * 1000:.0f}ms")

    if successful:
        avg_time = sum(r.elapsed_ms for r in successful) / len(successful)
        total_bytes = sum(r.content_length for r in successful)
        print(f"Avg response:   {avg_time:.0f}ms")
        print(f"Total bytes:    {total_bytes:,}")


async def main_async(args: argparse.Namespace) -> int:
    """Async main function."""
    fetcher = AsyncFetcher(
        max_concurrency=args.concurrency,
        timeout=args.timeout,
    )

    print(f"Fetching {len(args.urls)} URL(s) with concurrency={args.concurrency}...")
    print()

    start_time = time.perf_counter()
    results = await fetcher.fetch_all(args.urls)
    total_time = time.perf_counter() - start_time

    # Print individual results
    for result in results:
        print(result)
        print()

    # Print summary
    print_summary(results, total_time)

    # Return non-zero if any failed
    return 0 if all(r.success for r in results) else 1


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch URLs asynchronously with rate limiting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://api.github.com
  %(prog)s --concurrency 3 url1 url2 url3 url4 url5
  %(prog)s --timeout 5 https://httpbin.org/delay/3
        """,
    )

    parser.add_argument(
        "urls",
        nargs="+",
        help="URLs to fetch",
    )

    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=5,
        help="Maximum concurrent requests (default: 5)",
    )

    parser.add_argument(
        "-t", "--timeout",
        type=float,
        default=10.0,
        help="Request timeout in seconds (default: 10.0)",
    )

    args = parser.parse_args()

    # Validate URLs
    for url in args.urls:
        if not url.startswith(("http://", "https://")):
            print(f"Error: Invalid URL (must start with http:// or https://): {url}")
            return 1

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
