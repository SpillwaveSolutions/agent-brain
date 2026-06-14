/**
 * Server-free unit tests for corpus.ts — the Phase 61 smoke contract port.
 *
 * This file imports ONLY from ../src/corpus (no harness, no globalSetup,
 * no spawned process). It passes on any machine regardless of whether
 * OPENAI_API_KEY or agent-brain-serve/mcp binaries are present.
 *
 * Covers the full 5-shape assertNonEmptySearch dispatch matrix:
 *   Shape 1: MCP SDK CallToolResult (structuredContent + content variants)
 *   Shape 2: plain string (JSON + non-JSON)
 *   Shape 3: LlamaIndex ToolOutput (.raw_output / .raw_input)
 *   Shape 4: plain Array (truthy count)
 *   Shape 5: Autogen ToolResult (.result list)
 *   dict fallback: {total_results} | {results:[...]}
 *   0-count throws: search_documents returned 0 results
 *   null/undefined throws: returned None
 *   TOLERANCE: non-null unparseable envelope → count >=1 (passes)
 *
 * Phase 61 analogue: framework-matrix/_harness.py:_count + assert_non_empty_search
 */

import { describe, it, expect } from "vitest";
import {
  SMOKE_TOOL,
  SMOKE_QUERY,
  SMOKE_ARGS,
  FRAMEWORK_CORPUS,
  assertNonEmptySearch,
} from "../src/corpus.js";

// ---------------------------------------------------------------------------
// Smoke contract constants
// ---------------------------------------------------------------------------

describe("smoke contract constants", () => {
  it("SMOKE_TOOL === search_documents", () => {
    expect(SMOKE_TOOL).toBe("search_documents");
  });

  it("SMOKE_QUERY === authenticate user login", () => {
    expect(SMOKE_QUERY).toBe("authenticate user login");
  });

  it("SMOKE_ARGS deep-equals { query: SMOKE_QUERY }", () => {
    expect(SMOKE_ARGS).toEqual({ query: "authenticate user login" });
  });

  it("FRAMEWORK_CORPUS has exactly 4 keys", () => {
    expect(Object.keys(FRAMEWORK_CORPUS)).toHaveLength(4);
  });

  it("FRAMEWORK_CORPUS has auth.py", () => {
    expect(FRAMEWORK_CORPUS).toHaveProperty("auth.py");
  });

  it("FRAMEWORK_CORPUS has auth.md", () => {
    expect(FRAMEWORK_CORPUS).toHaveProperty("auth.md");
  });

  it("FRAMEWORK_CORPUS has query_service.py", () => {
    expect(FRAMEWORK_CORPUS).toHaveProperty("query_service.py");
  });

  it("FRAMEWORK_CORPUS has config.md", () => {
    expect(FRAMEWORK_CORPUS).toHaveProperty("config.md");
  });

  it("FRAMEWORK_CORPUS auth.py contains authenticate token", () => {
    expect(FRAMEWORK_CORPUS["auth.py"]).toContain("authenticate");
  });

  it("FRAMEWORK_CORPUS auth.md contains authenticate token", () => {
    expect(FRAMEWORK_CORPUS["auth.md"]).toContain("authenticate");
  });

  it("FRAMEWORK_CORPUS config.md contains authenticate token", () => {
    expect(FRAMEWORK_CORPUS["config.md"]).toContain("authenticate");
  });
});

// ---------------------------------------------------------------------------
// assertNonEmptySearch — 0-count and null throws
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — throws on 0 or null", () => {
  it("throws when total_results is 0", () => {
    expect(() => assertNonEmptySearch({ total_results: 0 })).toThrow(
      "search_documents returned 0 results"
    );
  });

  it("throws when results is empty array", () => {
    expect(() => assertNonEmptySearch({ results: [] })).toThrow(
      "search_documents returned 0 results"
    );
  });

  it("throws when envelope is null", () => {
    expect(() => assertNonEmptySearch(null)).toThrow();
  });

  it("throws when envelope is undefined", () => {
    expect(() => assertNonEmptySearch(undefined)).toThrow();
  });

  it("throws when plain array is empty", () => {
    expect(() => assertNonEmptySearch([])).toThrow(
      "search_documents returned 0 results"
    );
  });
});

// ---------------------------------------------------------------------------
// Shape 1: MCP SDK CallToolResult (structuredContent preferred)
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — Shape 1: MCP SDK CallToolResult", () => {
  it("passes for structuredContent.total_results = 2", () => {
    expect(() =>
      assertNonEmptySearch({ structuredContent: { total_results: 2 } })
    ).not.toThrow();
  });

  it("passes for structuredContent.results with 2 items", () => {
    expect(() =>
      assertNonEmptySearch({ structuredContent: { results: [{}, {}] } })
    ).not.toThrow();
  });

  it("passes for content list with JSON text block {results:[{},{}]}", () => {
    expect(() =>
      assertNonEmptySearch({
        content: [{ type: "text", text: '{"results":[{},{}]}' }],
      })
    ).not.toThrow();
  });

  it("passes for content list with JSON text block {total_results:3}", () => {
    expect(() =>
      assertNonEmptySearch({
        content: [{ type: "text", text: '{"total_results":3}' }],
      })
    ).not.toThrow();
  });

  it("passes for content as bare non-empty string", () => {
    expect(() =>
      assertNonEmptySearch({ content: "some text result" })
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Shape 2: plain string
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — Shape 2: plain string", () => {
  it("passes for JSON string {total_results:3}", () => {
    expect(() =>
      assertNonEmptySearch('{"total_results":3}')
    ).not.toThrow();
  });

  it("passes for non-empty non-JSON string (counts as 1)", () => {
    expect(() => assertNonEmptySearch("hit")).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Shape 3: LlamaIndex ToolOutput (.raw_output / .raw_input)
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — Shape 3: LlamaIndex ToolOutput", () => {
  it("passes for .raw_output with JSON {total_results:2}", () => {
    expect(() =>
      assertNonEmptySearch({ raw_output: '{"total_results":2}' })
    ).not.toThrow();
  });

  it("passes for .raw_input non-empty string", () => {
    expect(() =>
      assertNonEmptySearch({ raw_input: "some result" })
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Shape 4: plain Array
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — Shape 4: plain Array", () => {
  it("passes for [{}, {}] (2 truthy entries)", () => {
    expect(() => assertNonEmptySearch([{}, {}])).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Shape 5: Autogen ToolResult (.result list)
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — Shape 5: Autogen ToolResult", () => {
  it("passes for .result list with 1 entry", () => {
    expect(() =>
      assertNonEmptySearch({ result: [{ text: "some result" }] })
    ).not.toThrow();
  });

  it("passes for .result list with JSON content block", () => {
    expect(() =>
      assertNonEmptySearch({
        result: [{ type: "text", text: '{"total_results":2}' }],
      })
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// dict fallback
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — dict fallback", () => {
  it("passes for { total_results: 5 }", () => {
    expect(() => assertNonEmptySearch({ total_results: 5 })).not.toThrow();
  });

  it("passes for { results: [{}] }", () => {
    expect(() => assertNonEmptySearch({ results: [{}] })).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// TOLERANCE: non-null envelope that causes an extraction exception → count >=1 (passes)
//
// The tolerance branch mirrors _harness.py:assert_non_empty_search's `except`
// block: "any extraction failure on a non-None envelope is treated as >=1
// rather than raising the wrong error — the real failure surface is 0 results,
// not a shape-sniffing bug."
//
// In TypeScript, extraction errors are thrown exceptions (not bad return values).
// We simulate this by passing a Proxy that throws on property access.
// ---------------------------------------------------------------------------

describe("assertNonEmptySearch — TOLERANCE branch", () => {
  it("passes for a non-null envelope where extraction throws (exception = >=1)", () => {
    // Create a Proxy that throws on any property access to simulate an
    // extraction error (e.g., a frozen object with throwing getters).
    const throwingEnvelope = new Proxy(
      {},
      {
        get(_target, prop) {
          // Allow standard symbol access needed by JavaScript internals
          if (typeof prop === "symbol") return undefined;
          if (prop === "then") return undefined; // not a Promise
          throw new Error(`Simulated extraction error on property: ${String(prop)}`);
        },
      }
    );
    expect(() => assertNonEmptySearch(throwingEnvelope)).not.toThrow();
  });

  it("passes for non-null non-array object with .structuredContent that throws", () => {
    // Another tolerance test: structuredContent getter throws
    const envelope = Object.create(null) as Record<string, unknown>;
    Object.defineProperty(envelope, "structuredContent", {
      get() {
        throw new Error("Simulated getter error");
      },
      enumerable: true,
    });
    expect(() => assertNonEmptySearch(envelope)).not.toThrow();
  });
});
