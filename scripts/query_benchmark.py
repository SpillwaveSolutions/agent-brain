#!/usr/bin/env python3
"""Agent Brain query benchmark runner.

Standalone script for measuring query latency across all retrieval modes.
Hits the HTTP API (/query POST), not QueryService directly, so results
reflect user-visible end-to-end latency.

Usage:
    python scripts/query_benchmark.py [options]

Examples:
    # Basic benchmark against running server
    python scripts/query_benchmark.py

    # Prepare docs corpus then benchmark
    python scripts/query_benchmark.py --prepare-docs-corpus

    # JSON output for CI
    python scripts/query_benchmark.py --json

    # Specific modes only
    python scripts/query_benchmark.py --modes vector,bm25,hybrid

    # Custom server
    python scripts/query_benchmark.py --server-url http://localhost:9000
"""

import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

DEFAULT_SERVER_URL = "http://127.0.0.1:8000"
DEFAULT_ITERATIONS = 20
DEFAULT_WARMUPS = 3
DEFAULT_MODES = ["vector", "bm25", "hybrid", "graph", "multi"]
QUERIES_FILE = Path(__file__).parent / "benchmark_queries.json"
PREPARE_TIMEOUT_SECS = 300
POLL_INTERVAL_SECS = 2.0

# ---------------------------------------------------------------------------
# Explicit backend/mode support matrix.
# Each entry maps mode -> (supported, reason_if_unsupported).
# Ensures exactly 5 rows are always produced per benchmark run.
# ---------------------------------------------------------------------------

MODE_SUPPORT_MATRIX: dict[tuple[str, bool], dict[str, tuple[bool, str]]] = {
    ("chroma", True): {
        "vector": (True, ""),
        "bm25": (True, ""),
        "hybrid": (True, ""),
        "graph": (True, ""),
        "multi": (True, ""),
    },
    ("chroma", False): {
        "vector": (True, ""),
        "bm25": (True, ""),
        "hybrid": (True, ""),
        "graph": (False, "UNSUPPORTED: requires GraphRAG"),
        "multi": (True, ""),
    },
    ("postgres", True): {
        "vector": (True, ""),
        "bm25": (True, ""),
        "hybrid": (True, ""),
        "graph": (False, "UNSUPPORTED: Chroma-only"),
        "multi": (True, "graph contribution absent"),
    },
    ("postgres", False): {
        "vector": (True, ""),
        "bm25": (True, ""),
        "hybrid": (True, ""),
        "graph": (False, "UNSUPPORTED: Chroma-only"),
        "multi": (True, "graph contribution absent"),
    },
}


# ---------------------------------------------------------------------------
# Helper functions (small, testable)
# ---------------------------------------------------------------------------


def compute_stats(latencies: list[float]) -> dict[str, float]:
    """Compute descriptive statistics for a list of latency values (ms).

    Args:
        latencies: List of latency measurements in milliseconds.

    Returns:
        Dictionary with p50, p95, p99, mean, min, max, count, qps.
    """
    if not latencies:
        return {
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "count": 0,
            "qps": 0.0,
        }

    sorted_lat = sorted(latencies)
    n = len(sorted_lat)

    def percentile(p: float) -> float:
        """Compute percentile using nearest-rank method."""
        if n == 1:
            return sorted_lat[0]
        idx = max(0, min(n - 1, int(p / 100.0 * n)))
        return sorted_lat[idx]

    total_ms = sum(sorted_lat)
    qps = (n * 1000.0 / total_ms) if total_ms > 0 else 0.0

    return {
        "p50": percentile(50),
        "p95": percentile(95),
        "p99": percentile(99),
        "mean": statistics.mean(sorted_lat),
        "min": sorted_lat[0],
        "max": sorted_lat[-1],
        "count": float(n),
        "qps": qps,
    }


def format_mode_status(mode: str, status: str, reason: str = "") -> dict[str, str]:
    """Build a mode status dict.

    Args:
        mode: Retrieval mode name (e.g. "vector", "graph").
        status: Status string: "ok", "unsupported", "error".
        reason: Optional reason string for unsupported/error status.

    Returns:
        Dict with mode, status, reason keys.
    """
    return {"mode": mode, "status": status, "reason": reason}


def build_run_metadata(
    server_url: str,
    health_data: dict[str, Any],
    chunk_count: int,
    iterations: int,
    warmups: int,
    corpus_folders: list[str],
) -> dict[str, Any]:
    """Build benchmark run metadata dict.

    Args:
        server_url: Base URL of the Agent Brain server.
        health_data: Parsed JSON from GET /health endpoint.
        chunk_count: Number of indexed chunks from /query/count.
        iterations: Number of timed iterations per mode.
        warmups: Number of warm-up queries per mode.
        corpus_folders: List of indexed folder paths.

    Returns:
        Metadata dict suitable for inclusion in JSON output.
    """
    backend = health_data.get("storage_backend", "unknown")
    # GraphRAG enabled state may appear in /health/status graph_index section
    # or as a direct field; default to None (unknown) when absent.
    graph_enabled = health_data.get("graphrag_enabled", health_data.get("graph_enabled"))

    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "backend": backend,
        "graph_enabled": graph_enabled,
        "iterations": iterations,
        "warmups": warmups,
        "corpus_identity": corpus_folders,
        "chunk_count": chunk_count,
    }


def get_mode_support(
    backend: str,
    graph_enabled: bool | None,
    mode: str,
) -> tuple[bool, str]:
    """Check if a mode is supported on the given backend/graph config.

    Args:
        backend: Storage backend ("chroma" or "postgres").
        graph_enabled: Whether GraphRAG is enabled (None treated as False).
        mode: Retrieval mode name.

    Returns:
        Tuple of (is_supported, reason_string).
    """
    effective_graph = bool(graph_enabled)
    key = (backend.lower(), effective_graph)
    matrix = MODE_SUPPORT_MATRIX.get(key)
    if matrix is None:
        # Unknown backend — assume all modes supported
        return (True, "")
    entry = matrix.get(mode, (True, ""))
    return entry


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------


def run_preflight(server_url: str) -> dict[str, Any]:
    """Validate server and index state before benchmarking.

    Checks:
    - Server is reachable (GET /health)
    - Index is ready (GET /health/status)
    - Chunk count > 0 (GET /query/count)
    - Detects backend type and GraphRAG state

    Args:
        server_url: Base URL of the Agent Brain server.

    Returns:
        Dict with server_url, backend, graph_enabled, chunk_count,
        folders, warnings.

    Raises:
        SystemExit: If server is unreachable or chunk count is 0.
    """
    warnings: list[str] = []

    # 1. Server reachable
    try:
        resp = httpx.get(f"{server_url}/health/", timeout=10.0)
        resp.raise_for_status()
        health_data = resp.json()
    except httpx.ConnectError:
        console.print(
            f"[bold red]ERROR:[/] Cannot reach server at {server_url}. "
            "Start the server first with `agent-brain start`."
        )
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        console.print(
            f"[bold red]ERROR:[/] Server returned {exc.response.status_code} "
            f"from /health: {exc.response.text}"
        )
        sys.exit(1)
    except Exception as exc:
        console.print(f"[bold red]ERROR:[/] Failed to contact server: {exc}")
        sys.exit(1)

    backend = health_data.get("storage_backend", "chroma")
    graph_enabled = health_data.get(
        "graphrag_enabled", health_data.get("graph_enabled")
    )

    # 2. Index ready state
    try:
        status_resp = httpx.get(f"{server_url}/health/status", timeout=10.0)
        status_data = status_resp.json()
        if status_data.get("indexing_in_progress"):
            warnings.append(
                "Index is currently being built — results may be incomplete."
            )
        # Try to determine graph state from status if not in health
        if graph_enabled is None and status_data.get("graph_index"):
            graph_enabled = status_data["graph_index"].get("enabled")
    except Exception:
        warnings.append("Could not retrieve /health/status — skipping readiness check.")
        status_data = {}

    # 3. Chunk count
    try:
        count_resp = httpx.get(f"{server_url}/query/count", timeout=10.0)
        count_data = count_resp.json()
        chunk_count = count_data.get("total_chunks", count_data.get("count", 0))
    except Exception:
        chunk_count = 0

    if chunk_count == 0:
        console.print(
            "[bold red]ERROR:[/] Index is empty (chunk count = 0). "
            "Index documents first, or use --prepare-docs-corpus."
        )
        sys.exit(1)

    # 4. Indexed folders
    folders: list[str] = []
    try:
        folders_resp = httpx.get(f"{server_url}/index/folders/", timeout=10.0)
        if folders_resp.status_code == 200:
            folders_data = folders_resp.json()
            folders = [f.get("folder_path", "") for f in folders_data.get("folders", [])]
    except Exception:
        # Folders endpoint optional — fall back to indexed_folders in status
        folders = status_data.get("indexed_folders", [])

    # Warn if docs/ not in corpus
    docs_indexed = any("docs" in f for f in folders)
    if not docs_indexed and folders:
        warnings.append(
            "Active corpus does not include docs/ -- results are not a baseline."
        )

    return {
        "server_url": server_url,
        "backend": backend,
        "graph_enabled": graph_enabled,
        "chunk_count": chunk_count,
        "folders": folders,
        "warnings": warnings,
        "health_data": health_data,
    }


# ---------------------------------------------------------------------------
# Setup mode
# ---------------------------------------------------------------------------


def prepare_docs_corpus(server_url: str, docs_path: str) -> None:
    """Reset index and re-index the docs/ folder.

    Steps:
    1. DELETE /index to clear all data.
    2. POST /index with docs_path.
    3. Poll /health/status until status ready (timeout 300 s).

    Args:
        server_url: Base URL of the Agent Brain server.
        docs_path: Absolute path to the docs/ folder to index.

    Raises:
        SystemExit: On HTTP errors or timeout.
    """
    console.print(f"[bold cyan]Preparing docs corpus from:[/] {docs_path}")

    # Reset index
    console.print("  Clearing index...")
    try:
        del_resp = httpx.delete(f"{server_url}/index/", timeout=30.0)
        del_resp.raise_for_status()
        console.print("  [green]Index cleared.[/]")
    except Exception as exc:
        console.print(f"  [yellow]Warning:[/] Could not clear index: {exc}")

    # Trigger indexing
    console.print(f"  Starting indexing of {docs_path}...")
    try:
        idx_resp = httpx.post(
            f"{server_url}/index/",
            params={"allow_external": "true"},
            json={"folder_path": docs_path},
            timeout=30.0,
        )
        idx_resp.raise_for_status()
        job_data = idx_resp.json()
        job_id = job_data.get("job_id", "unknown")
        console.print(f"  [green]Indexing job started:[/] {job_id}")
    except httpx.HTTPStatusError as exc:
        console.print(
            f"  [bold red]ERROR:[/] Failed to start indexing: {exc.response.text}"
        )
        sys.exit(1)
    except Exception as exc:
        console.print(f"  [bold red]ERROR:[/] {exc}")
        sys.exit(1)

    # Poll until ready
    deadline = time.monotonic() + PREPARE_TIMEOUT_SECS
    console.print("  Waiting for indexing to complete...")
    while time.monotonic() < deadline:
        try:
            st_resp = httpx.get(f"{server_url}/health/status", timeout=10.0)
            st_data = st_resp.json()
            if not st_data.get("indexing_in_progress", True):
                chunk_count = st_data.get("total_chunks", 0)
                console.print(
                    f"  [green]Indexing complete.[/] {chunk_count} chunks indexed."
                )
                return
        except Exception:
            pass
        time.sleep(POLL_INTERVAL_SECS)

    console.print(
        f"  [bold red]ERROR:[/] Indexing did not complete within "
        f"{PREPARE_TIMEOUT_SECS}s."
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


def benchmark_mode(
    server_url: str,
    mode: str,
    queries: list[str],
    iterations: int,
    warmups: int,
) -> dict[str, Any]:
    """Benchmark a single retrieval mode.

    Sends warm-up queries (discarded), then timed queries, collecting
    client-observed latency and server-reported query_time_ms.

    Args:
        server_url: Base URL of the Agent Brain server.
        mode: Retrieval mode string (vector, bm25, hybrid, graph, multi).
        queries: List of query strings to cycle through.
        iterations: Number of timed iterations.
        warmups: Number of warm-up iterations (results discarded).

    Returns:
        Dict with mode, status, client_stats, server_stats, reason.
    """
    client_latencies: list[float] = []
    server_latencies: list[float] = []

    def _post_query(query: str) -> tuple[float, float | None, int]:
        """Post a query and return (client_ms, server_ms, status_code)."""
        payload = {"query": query, "mode": mode, "top_k": 5}
        start = time.perf_counter()
        resp = httpx.post(
            f"{server_url}/query/",
            json=payload,
            timeout=30.0,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        server_ms: float | None = None
        if resp.status_code == 200:
            data = resp.json()
            server_ms = data.get("query_time_ms")
        return elapsed_ms, server_ms, resp.status_code

    # Warm-up passes (discard timing)
    for i in range(warmups):
        q = queries[i % len(queries)]
        try:
            _, _, status_code = _post_query(q)
            if status_code in (400, 422, 501):
                # Mode unsupported — no need to continue warm-ups
                break
        except Exception:
            break

    # Timed iterations
    unsupported_reason = ""
    for i in range(iterations):
        q = queries[i % len(queries)]
        try:
            client_ms, server_ms, status_code = _post_query(q)
        except Exception as exc:
            return {
                "mode": mode,
                "status": "error",
                "client_stats": compute_stats([]),
                "server_stats": compute_stats([]),
                "reason": str(exc),
            }

        if status_code in (400, 422, 501):
            # Unsupported mode — extract reason from response body if possible
            try:
                err_data = httpx.post(
                    f"{server_url}/query/",
                    json={"query": q, "mode": mode, "top_k": 5},
                    timeout=30.0,
                ).json()
                unsupported_reason = err_data.get("detail", f"HTTP {status_code}")
            except Exception:
                unsupported_reason = f"HTTP {status_code}"
            return {
                "mode": mode,
                "status": "unsupported",
                "client_stats": compute_stats([]),
                "server_stats": compute_stats([]),
                "reason": unsupported_reason,
            }
        elif status_code >= 500:
            unsupported_reason = f"Server error HTTP {status_code}"
            return {
                "mode": mode,
                "status": "error",
                "client_stats": compute_stats([]),
                "server_stats": compute_stats([]),
                "reason": unsupported_reason,
            }

        client_latencies.append(client_ms)
        if server_ms is not None:
            server_latencies.append(server_ms)

    return {
        "mode": mode,
        "status": "ok",
        "client_stats": compute_stats(client_latencies),
        "server_stats": compute_stats(server_latencies),
        "reason": "",
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_results_table(results: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    """Print benchmark results as a Rich table with metadata header.

    Args:
        results: List of mode result dicts from benchmark_mode.
        metadata: Run metadata dict from build_run_metadata.
    """
    console.print()
    console.print("[bold]Agent Brain Query Benchmark[/]")
    console.print(
        f"  Date:    {metadata.get('date', 'N/A')}\n"
        f"  Backend: {metadata.get('backend', 'N/A')}  |  "
        f"GraphRAG: {metadata.get('graph_enabled', 'N/A')}\n"
        f"  OS:      {metadata.get('os', 'N/A')}  |  "
        f"Python: {metadata.get('python_version', 'N/A')}\n"
        f"  Chunks:  {metadata.get('chunk_count', 0)}  |  "
        f"Iterations: {metadata.get('iterations', 0)}  |  "
        f"Warmups: {metadata.get('warmups', 0)}"
    )
    corpus = metadata.get("corpus_identity", [])
    if corpus:
        console.print(f"  Corpus:  {', '.join(corpus)}")
    console.print()

    table = Table(
        title="Client-Observed Latency (ms)",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Mode", style="cyan", no_wrap=True)
    table.add_column("Status", style="white")
    table.add_column("p50 (ms)", justify="right")
    table.add_column("p95 (ms)", justify="right")
    table.add_column("p99 (ms)", justify="right")
    table.add_column("Mean (ms)", justify="right")
    table.add_column("QPS", justify="right")

    for r in results:
        mode = r["mode"]
        status = r["status"]
        cs = r.get("client_stats", {})

        if status == "ok":
            status_str = "[green]ok[/]"
            p50 = f"{cs.get('p50', 0):.1f}"
            p95 = f"{cs.get('p95', 0):.1f}"
            p99 = f"{cs.get('p99', 0):.1f}"
            mean = f"{cs.get('mean', 0):.1f}"
            qps = f"{cs.get('qps', 0):.2f}"
        elif status == "unsupported":
            status_str = "[yellow]unsupported[/]"
            reason = r.get("reason", "")
            p50 = p95 = p99 = mean = qps = f"[dim]{reason[:20]}[/]" if reason else "-"
        elif status == "skipped":
            status_str = "[dim]skipped[/]"
            p50 = p95 = p99 = mean = qps = "[dim]-[/]"
        else:
            status_str = "[red]error[/]"
            p50 = p95 = p99 = mean = qps = "-"

        table.add_row(mode, status_str, p50, p95, p99, mean, qps)

    console.print(table)

    # Server-reported timing table (secondary signal)
    server_results = [r for r in results if r["status"] == "ok"]
    if server_results:
        server_table = Table(
            title="Server-Reported query_time_ms (secondary signal)",
            show_header=True,
            header_style="bold blue",
        )
        server_table.add_column("Mode", style="cyan", no_wrap=True)
        server_table.add_column("p50 (ms)", justify="right")
        server_table.add_column("p95 (ms)", justify="right")
        server_table.add_column("p99 (ms)", justify="right")
        server_table.add_column("Mean (ms)", justify="right")

        for r in server_results:
            ss = r.get("server_stats", {})
            server_table.add_row(
                r["mode"],
                f"{ss.get('p50', 0):.1f}",
                f"{ss.get('p95', 0):.1f}",
                f"{ss.get('p99', 0):.1f}",
                f"{ss.get('mean', 0):.1f}",
            )

        console.print(server_table)


def build_json_output(
    results: list[dict[str, Any]], metadata: dict[str, Any]
) -> dict[str, Any]:
    """Build full JSON output payload.

    Args:
        results: List of mode result dicts from benchmark_mode.
        metadata: Run metadata dict from build_run_metadata.

    Returns:
        Dict with metadata, results, unsupported_modes keys.
    """
    unsupported = [r for r in results if r["status"] == "unsupported"]
    supported = [r for r in results if r["status"] == "ok"]

    return {
        "metadata": metadata,
        "results": results,
        "supported_modes": [r["mode"] for r in supported],
        "unsupported_modes": [
            {"mode": r["mode"], "reason": r.get("reason", "")} for r in unsupported
        ],
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Agent Brain query benchmark."""
    parser = argparse.ArgumentParser(
        description="Agent Brain query benchmark runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--server-url",
        default=os.environ.get("AGENT_BRAIN_URL", DEFAULT_SERVER_URL),
        help=f"Agent Brain server URL (default: {DEFAULT_SERVER_URL})",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of timed queries per mode (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--warmups",
        type=int,
        default=DEFAULT_WARMUPS,
        help=f"Number of warm-up queries before timing (default: {DEFAULT_WARMUPS})",
    )
    parser.add_argument(
        "--modes",
        default=",".join(DEFAULT_MODES),
        help="Comma-separated list of modes to benchmark "
        f"(default: {','.join(DEFAULT_MODES)})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (suitable for CI)",
    )
    parser.add_argument(
        "--prepare-docs-corpus",
        action="store_true",
        help="Reset index, index docs/ folder, wait for completion before benchmarking",
    )
    parser.add_argument(
        "--queries-file",
        default=str(QUERIES_FILE),
        help=f"Path to query set JSON file (default: {QUERIES_FILE})",
    )
    parser.add_argument(
        "--docs-path",
        default=str(Path(__file__).parent.parent / "docs"),
        help="Path to docs/ folder (used with --prepare-docs-corpus)",
    )

    args = parser.parse_args()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    # Load query set
    queries_path = Path(args.queries_file)
    if not queries_path.exists():
        console.print(
            f"[bold red]ERROR:[/] Query file not found: {queries_path}\n"
            "Use --queries-file to specify an alternate path."
        )
        sys.exit(1)

    with open(queries_path) as f:
        query_data = json.load(f)

    queries: list[str] = query_data.get("queries", [])
    if not queries:
        console.print("[bold red]ERROR:[/] Query file contains no queries.")
        sys.exit(1)

    # Optional corpus preparation
    if args.prepare_docs_corpus:
        prepare_docs_corpus(args.server_url, args.docs_path)

    # Preflight checks
    preflight = run_preflight(args.server_url)

    if preflight["warnings"] and not args.json_output:
        for warn in preflight["warnings"]:
            console.print(f"[yellow]WARNING:[/] {warn}")

    # Build metadata — merge preflight-resolved backend/graph info into
    # health_data so build_run_metadata can read them (the basic /health/
    # endpoint does not expose storage_backend or graph_enabled directly).
    merged_health = dict(preflight["health_data"])
    merged_health["storage_backend"] = preflight["backend"]
    merged_health["graph_enabled"] = preflight["graph_enabled"]
    metadata = build_run_metadata(
        server_url=args.server_url,
        health_data=merged_health,
        chunk_count=preflight["chunk_count"],
        iterations=args.iterations,
        warmups=args.warmups,
        corpus_folders=preflight["folders"],
    )

    if not args.json_output:
        console.print(
            f"\n[bold]Running benchmark:[/] "
            f"{args.iterations} iterations x {args.warmups} warmups "
            f"across {len(DEFAULT_MODES)} modes (always 5 rows)"
        )

    # Run benchmarks — always iterate ALL 5 DEFAULT_MODES to guarantee 5 rows.
    # Modes not requested by the user are marked "skipped".
    # Modes unsupported by the backend/graph config are short-circuited via
    # MODE_SUPPORT_MATRIX without hitting the HTTP endpoint.
    all_results: list[dict[str, Any]] = []
    backend = preflight.get("backend", "chroma")
    graph_enabled = preflight.get("graph_enabled")

    for mode in DEFAULT_MODES:
        # Check if the user requested this mode (or all modes if not filtered)
        user_requested = mode in modes

        if not user_requested:
            # Produce a "skipped" row without benchmarking
            all_results.append(
                {
                    "mode": mode,
                    "status": "skipped",
                    "client_stats": compute_stats([]),
                    "server_stats": compute_stats([]),
                    "reason": "not in --modes list",
                }
            )
            if not args.json_output:
                console.print(
                    f"  Benchmarking mode: [cyan]{mode}[/]... [dim]skipped[/]"
                )
            continue

        # Check support matrix before hitting the endpoint
        supported, matrix_reason = get_mode_support(backend, graph_enabled, mode)
        if not supported:
            all_results.append(
                {
                    "mode": mode,
                    "status": "unsupported",
                    "client_stats": compute_stats([]),
                    "server_stats": compute_stats([]),
                    "reason": matrix_reason,
                }
            )
            if not args.json_output:
                console.print(
                    f"  Benchmarking mode: [cyan]{mode}[/]... "
                    f"[yellow]unsupported[/] — {matrix_reason}"
                )
            continue

        # Mode is supported — run the actual benchmark
        if not args.json_output:
            console.print(f"  Benchmarking mode: [cyan]{mode}[/]...", end=" ")
        result = benchmark_mode(
            server_url=args.server_url,
            mode=mode,
            queries=queries,
            iterations=args.iterations,
            warmups=args.warmups,
        )
        # If mode has an annotation from the matrix (supported=True but
        # non-empty reason), append it to the result reason.
        if matrix_reason and not result.get("reason"):
            result["reason"] = matrix_reason
        all_results.append(result)
        if not args.json_output:
            status = result["status"]
            if status == "ok":
                p50 = result["client_stats"].get("p50", 0)
                reason_note = f" [{result['reason']}]" if result.get("reason") else ""
                console.print(f"[green]done[/] (p50={p50:.1f}ms){reason_note}")
            elif status == "unsupported":
                console.print(f"[yellow]unsupported[/] — {result.get('reason', '')}")
            else:
                console.print(f"[red]error[/] — {result.get('reason', '')}")

    # Output
    if args.json_output:
        output = build_json_output(all_results, metadata)
        print(json.dumps(output, indent=2))
    else:
        print_results_table(all_results, metadata)


if __name__ == "__main__":
    main()
