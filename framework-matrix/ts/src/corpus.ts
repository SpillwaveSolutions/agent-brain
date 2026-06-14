/**
 * Phase 61 smoke contract — TypeScript port.
 *
 * Canonical source: framework-matrix/_harness.py
 * Values are byte-identical to the Python FRAMEWORK_CORPUS / SMOKE_QUERY /
 * SMOKE_TOOL / SMOKE_ARGS / _count / assert_non_empty_search.
 *
 * No external imports — this module is pure and server-free, so
 * test/corpus.test.ts can run on any machine without OPENAI_API_KEY or
 * agent-brain-serve/mcp on PATH.
 */

// ---------------------------------------------------------------------------
// Tiny corpus — guarantees a non-empty search hit against "authenticate".
// Mirror of framework-matrix/_harness.py:FRAMEWORK_CORPUS (exact contents).
// ---------------------------------------------------------------------------

export const FRAMEWORK_CORPUS: Record<string, string> = {
  "auth.py": `"""Authentication utilities for the example service."""


def authenticate(username: str, password: str) -> bool:
    """Authenticate a user by username and password.

    Returns True when credentials are valid, False otherwise.
    The login workflow calls this function on every user login attempt.
    """
    # Placeholder: delegate to identity provider.
    return username != "" and password != ""


def logout(user_id: str) -> None:
    """Terminate the authenticated session for user_id."""
    pass
`,

  "auth.md": `# Authentication Guide

This document explains how to authenticate users in the system.

## Overview

The \`authenticate\` function verifies user credentials during the login
workflow. Call it with the user's username and password; it returns
\`True\` when the credentials are valid.

## Usage

\`\`\`python
from auth import authenticate

if authenticate(username, password):
    print("login successful")
else:
    print("authentication failed")
\`\`\`

## Security Notes

- Passwords are never stored in plaintext.
- Failed login attempts are logged for auditing.
- Use HTTPS to protect credentials in transit.
`,

  "query_service.py": `"""Query service for the document retrieval pipeline."""


def search(query: str, top_k: int = 10) -> list[dict]:
    """Search the indexed corpus for documents matching the query.

    Args:
        query: Natural-language search query.
        top_k: Maximum number of results to return.

    Returns:
        List of result dicts with keys: text, source, score, chunk_id.
    """
    # Delegate to the vector + BM25 hybrid retrieval backend.
    return []


def count_documents() -> int:
    """Return the total number of indexed document chunks."""
    return 0
`,

  "config.md": `# Configuration Reference

## Environment Variables

- \`OPENAI_API_KEY\` — required for embedding generation
- \`AGENT_BRAIN_STATE_DIR\` — override the default state directory
- \`API_PORT\` — HTTP server port (default 8000)
- \`API_HOST\` — HTTP server host (default 127.0.0.1)

## Authenticate Endpoint

The \`/authenticate\` endpoint accepts Bearer tokens for API access.
Include \`Authorization: Bearer <token>\` in all authenticated requests.
`,
};

// ---------------------------------------------------------------------------
// Canonical smoke-test parameters — every framework adapter uses these.
// Mirror of framework-matrix/_harness.py:SMOKE_QUERY/SMOKE_TOOL/SMOKE_ARGS.
// ---------------------------------------------------------------------------

export const SMOKE_QUERY: string = "authenticate user login";
export const SMOKE_TOOL: string = "search_documents";
export const SMOKE_ARGS = { query: SMOKE_QUERY } as const;

// ---------------------------------------------------------------------------
// Result-shape normalization helpers (private).
// Ports _count_payload, _count_text, _count_content_list, _count_list, _count
// from framework-matrix/_harness.py VERBATIM (shape dispatch order preserved).
// ---------------------------------------------------------------------------

function _countPayload(d: unknown): number {
  if (typeof d !== "object" || d === null || Array.isArray(d)) {
    return 0;
  }
  const obj = d as Record<string, unknown>;
  if ("total_results" in obj) {
    const n = Number(obj["total_results"]);
    if (!isNaN(n)) {
      return n;
    }
  }
  const results = obj["results"];
  if (Array.isArray(results)) {
    return results.length;
  }
  return 0;
}

function _countText(s: unknown): number {
  if (typeof s !== "string") return 0;
  const stripped = s.trim();
  if (!stripped) return 0;
  try {
    const parsed: unknown = JSON.parse(stripped);
    return _countPayload(parsed);
  } catch {
    // Non-empty non-JSON text is treated as >=1 result.
    return 1;
  }
}

function _countContentList(lst: unknown): number {
  if (!Array.isArray(lst) || lst.length === 0) return 0;
  const block = lst[0] as Record<string, unknown> | null | undefined;
  if (block === null || block === undefined) return 1;
  // Object with .text attribute (MCP SDK TextContent / TextResultContent).
  let text: unknown =
    typeof block === "object" && !Array.isArray(block) && "text" in block
      ? (block as Record<string, unknown>)["text"]
      : undefined;
  if (typeof text !== "string" && typeof block === "object") {
    text = (block as Record<string, unknown>)["text"];
  }
  if (typeof text === "string" && text.trim()) {
    return _countText(text);
  }
  // Content block without text — non-empty list counts as >=1.
  return lst.length > 0 ? 1 : 0;
}

function _countList(lst: unknown): number {
  if (!Array.isArray(lst)) return 0;
  return lst.filter((x) => Boolean(x)).length;
}

/**
 * Normalize any of the 5 framework result shapes to an integer count.
 *
 * Shape dispatch order (mirrors _harness.py:_count VERBATIM):
 *
 * 1. MCP SDK CallToolResult (structuredContent preferred; content fallback).
 * 2. LangChain ToolMessage / bare string.
 * 3. LlamaIndex ToolOutput (.raw_output / .raw_input).
 * 4. Pydantic AI content parts / plain result list.
 * 5. Autogen McpWorkbench ToolResult (.result list).
 * dict fallback (structuredContent already-unwrapped or raw dict).
 */
function _count(results: unknown): number {
  // ------------------------------------------------------------------
  // Shape 1: MCP SDK CallToolResult (structuredContent preferred)
  // ------------------------------------------------------------------
  if (typeof results === "object" && results !== null && !Array.isArray(results)) {
    const obj = results as Record<string, unknown>;

    const sc = obj["structuredContent"];
    if (sc !== undefined) {
      return _countPayload(sc);
    }

    const content = obj["content"];
    if (content !== undefined) {
      if (Array.isArray(content)) {
        return _countContentList(content);
      }
      if (typeof content === "string") {
        return _countText(content);
      }
    }
  }

  // ------------------------------------------------------------------
  // Shape 2: LangChain bare str result
  // ------------------------------------------------------------------
  if (typeof results === "string") {
    return _countText(results);
  }

  if (typeof results === "object" && results !== null && !Array.isArray(results)) {
    const obj = results as Record<string, unknown>;

    // ------------------------------------------------------------------
    // Shape 3: LlamaIndex ToolOutput (.raw_output / .raw_input)
    // ------------------------------------------------------------------
    for (const attr of ["raw_output", "raw_input"]) {
      const v = obj[attr];
      if (v !== undefined) {
        if (typeof v === "string") {
          return _countText(v);
        }
        return _countPayload(v);
      }
    }

    // ------------------------------------------------------------------
    // Shape 5: Autogen McpWorkbench ToolResult (.result list)
    // (checked before plain-array shape 4 since this object is non-array)
    // ------------------------------------------------------------------
    const tr = obj["result"];
    if (tr !== undefined) {
      return _countContentList(tr);
    }

    // ------------------------------------------------------------------
    // dict fallback (structuredContent already-unwrapped or raw dict)
    // ------------------------------------------------------------------
    return _countPayload(results);
  }

  // ------------------------------------------------------------------
  // Shape 4: Pydantic AI list of content parts OR plain result list
  // ------------------------------------------------------------------
  if (Array.isArray(results)) {
    return _countList(results);
  }

  return 0;
}

// ---------------------------------------------------------------------------
// Public assertion helper.
// Ports assert_non_empty_search from framework-matrix/_harness.py VERBATIM.
// ---------------------------------------------------------------------------

/**
 * Assert that a framework's search_documents call returned >=1 result.
 *
 * Normalizes all 5 framework result shapes (MCP SDK CallToolResult,
 * LangChain ToolMessage/str, LlamaIndex ToolOutput, Pydantic AI content
 * parts, Autogen McpWorkbench ToolResult) to an integer count, then
 * asserts count >= 1.
 *
 * TOLERANCE: any extraction error on a NON-null/undefined envelope is
 * treated as count>=1 (do NOT throw a shape-sniffing error). Only throw
 * the "0 results" error when the count is genuinely 0; throw the
 * "returned None" error when the envelope is null/undefined.
 *
 * @param results - The raw return value from a framework's call_tool /
 *   invoke / run call against the search_documents tool.
 * @throws Error when count is 0 (message contains "search_documents returned 0 results")
 * @throws Error when envelope is null/undefined
 */
export function assertNonEmptySearch(results: unknown): void {
  if (results === null || results === undefined) {
    throw new Error(
      `search_documents returned None — expected a result envelope`
    );
  }

  let count: number;
  try {
    count = _count(results);
  } catch {
    // Any extraction failure on a non-null/undefined envelope is treated
    // as >=1 (tolerant — the real failure surface is 0 results, not a
    // shape-sniffing bug). Mirror of _harness.py:assert_non_empty_search
    // except block.
    return;
  }

  if (count < 1) {
    throw new Error(
      `search_documents returned 0 results against the seeded corpus. ` +
        `Result envelope: ${JSON.stringify(results)}`
    );
  }
}
