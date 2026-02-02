#!/usr/bin/env python3
"""
Query the Doc-Serve server for domain-specific documentation.

Usage:
    python query_domain.py "your search query" [--top-k 5] [--threshold 0.7]

Example:
    python query_domain.py "how to configure pod networking" --top-k 10
"""

import argparse
import json
import os
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)


def get_base_url() -> str:
    """Get the Doc-Serve server URL from environment or default."""
    return os.environ.get("DOC_SERVE_URL", "http://127.0.0.1:8000")


def check_health(base_url: str) -> dict:
    """Check server health status."""
    try:
        response = httpx.get(f"{base_url}/health", timeout=10.0)
        return response.json()
    except httpx.ConnectError:
        return {"status": "unreachable", "message": "Cannot connect to server"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def query_documents(
    base_url: str,
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.7
) -> dict:
    """Execute a semantic search query."""
    try:
        response = httpx.post(
            f"{base_url}/query",
            json={
                "query": query,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold
            },
            timeout=30.0
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 503:
            return {"error": "Server not ready", "detail": response.json().get("detail")}
        elif response.status_code == 400:
            return {"error": "Invalid query", "detail": response.json().get("detail")}
        else:
            return {"error": f"HTTP {response.status_code}", "detail": response.text}

    except httpx.ConnectError:
        return {"error": "Connection failed", "detail": "Cannot connect to server"}
    except Exception as e:
        return {"error": "Request failed", "detail": str(e)}


def format_results(results: dict, query: str) -> str:
    """Format query results for display."""
    output = []

    if "error" in results:
        output.append(f"Error: {results['error']}")
        if "detail" in results:
            output.append(f"Detail: {results['detail']}")
        return "\n".join(output)

    total = results.get("total_results", 0)
    query_time = results.get("query_time_ms", 0)

    output.append(f"Query: {query}")
    output.append(f"Found {total} results in {query_time:.1f}ms")
    output.append("-" * 60)

    for i, result in enumerate(results.get("results", []), 1):
        source = result.get('source', 'Unknown')
        # Clean up source path for display
        display_source = os.path.basename(source) if '/' in source else source
        output.append(f"\n[{i}] Source: {display_source}")
        output.append(f"    Full Path: {source}")
        output.append(f"    Similarity Score: {result.get('score', 0):.4f}")
        text = result.get('text', '')
        # Indent text for better readability
        indented_text = "\n    ".join(text[:500].split("\n"))
        output.append(f"    Content:\n    {indented_text}...")
        output.append("-" * 40)

    if total == 0:
        output.append("\nNo matching documents found.")
        output.append("Try adjusting your query or lowering the similarity threshold.")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Query Doc-Serve for domain documentation"
    )
    parser.add_argument("query", help="Search query text")
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.7,
        help="Similarity threshold 0.0-1.0 (default: 0.7)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--url",
        help="Server URL (default: DOC_SERVE_URL env or http://127.0.0.1:8000)"
    )

    args = parser.parse_args()

    base_url = args.url or get_base_url()

    # Check health first
    health = check_health(base_url)
    if health.get("status") not in ["healthy", "indexing"]:
        if args.json:
            print(json.dumps({"error": "Server unavailable", "health": health}, indent=2))
        else:
            print(f"Server unavailable: {health.get('message', 'Unknown error')}")
        sys.exit(1)

    # Execute query
    results = query_documents(
        base_url,
        args.query,
        top_k=args.top_k,
        similarity_threshold=args.threshold
    )

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(format_results(results, args.query))

    # Exit with error code if query failed
    if "error" in results:
        sys.exit(1)


if __name__ == "__main__":
    main()
