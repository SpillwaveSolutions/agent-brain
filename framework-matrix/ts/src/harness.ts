/**
 * Shared MCP subprocess fixture for the Phase 62 TypeScript framework matrix.
 *
 * Canonical sources (audit trail):
 *   - framework-matrix/conftest.py   (seeded-server flow, SIGTERM teardown,
 *                                     grace timings, stray-MCP cleanup)
 *   - framework-matrix/_harness.py   (stdio_server_params, prerequisites_available)
 *
 * Port rules:
 *   - GRACE TIMING mirrors conftest.py EXACTLY:
 *       agent-brain-serve SERVER teardown → graceMs = 10000
 *         (conftest.py start_seeded_server: proc.wait(timeout=10))
 *       lighter HTTP / MCP-child path   → graceMs = 5000
 *         (conftest.py _HTTP_LISTENER_GRACE_S = 5.0)
 *   - SIGTERM is ALWAYS the first signal — NEVER SIGINT.
 *     (Phase 60 contract; SIGINT would only appear in comments.)
 *   - Node 18+ global fetch is used for HTTP health polling / index trigger.
 *   - AF_UNIX socket-path limit (104 chars on macOS) is sidestepped by
 *     globalSetup using a short "abfwm-" prefixed temp dir, mirroring
 *     conftest.py's tempfile.mkdtemp(prefix="abfwm-").
 */

import { execFileSync } from "node:child_process";
import { spawn, ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { FRAMEWORK_CORPUS } from "./corpus.js";

// ---------------------------------------------------------------------------
// Timeout constants (mirrors conftest.py)
// ---------------------------------------------------------------------------

const SERVER_STARTUP_TIMEOUT_MS = 60_000;
const INDEXING_TIMEOUT_MS = 180_000;
const HEALTH_POLL_INTERVAL_MS = 1_000;

// ---------------------------------------------------------------------------
// Free-port helper — mirrors conftest.py:_find_free_port()
// ---------------------------------------------------------------------------

/**
 * Bind a net.Server to port 0 on 127.0.0.1, read the assigned port, close.
 */
export function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => reject(new Error("Could not get port from server")));
        return;
      }
      const port = address.port;
      server.close(() => resolve(port));
    });
    server.once("error", reject);
  });
}

// ---------------------------------------------------------------------------
// Prerequisites check — mirrors conftest.py:prerequisites_available()
// and _harness.py:stdio_server_params (which does shutil.which internally).
// ---------------------------------------------------------------------------

/**
 * Return {ok, reason} for the full set of integration test requirements.
 *
 * Returns {ok: true, reason: ""} when every prerequisite is present.
 * Returns {ok: false, reason: "..."} when something is missing — the caller
 * passes reason to vitest ctx.skip() so CI logs show why the test skipped.
 */
export function prerequisitesAvailable(): { ok: boolean; reason: string } {
  if (!process.env["OPENAI_API_KEY"]) {
    return {
      ok: false,
      reason:
        "OPENAI_API_KEY not set — the framework matrix requires a real " +
        "embedding provider to seed the corpus so search_documents " +
        "returns non-empty results.",
    };
  }
  if (!_which("agent-brain-serve")) {
    return {
      ok: false,
      reason:
        "agent-brain-serve not on PATH — install agent-brain-server " +
        "into the active Python environment.",
    };
  }
  if (!_which("agent-brain-mcp")) {
    return {
      ok: false,
      reason:
        "agent-brain-mcp not on PATH — install agent-brain-mcp " +
        "(agent-brain-ag-mcp on PyPI) into the active Python environment.",
    };
  }
  return { ok: true, reason: "" };
}

function _which(binary: string): string | null {
  try {
    const result = execFileSync("which", [binary], {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return result.trim() || null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// stdio launch spec — mirrors _harness.py:stdio_server_params() VERBATIM.
// ---------------------------------------------------------------------------

export interface StdioServerParams {
  command: string;
  args: string[];
  env: Record<string, string>;
}

/**
 * Return {command, args, env} for spawning agent-brain-mcp over stdio.
 *
 * Mirrors _harness.py:stdio_server_params() — the single stdio launch spec
 * that BOTH framework tests (FRAME-06 Mastra, FRAME-07 Vercel AI SDK) consume.
 *
 * @param stateDir - The session-scoped state directory (set by globalSetup).
 *   The UDS socket lives at stateDir/.agent-brain/agent-brain.sock.
 */
export function stdioServerParams(stateDir: string): StdioServerParams {
  const binary = _which("agent-brain-mcp") ?? "agent-brain-mcp";
  const agentBrainState = join(stateDir, ".agent-brain");
  const args = ["--backend", "uds", "--state-dir", agentBrainState];

  const env: Record<string, string> = {
    PATH: process.env["PATH"] ?? "",
    HOME: process.env["HOME"] ?? "",
    AGENT_BRAIN_STATE_DIR: agentBrainState,
  };
  // Forward OPENAI_API_KEY when present — the MCP server needs it for
  // embedding on search_documents calls. Mirrors _harness.py exactly.
  if (process.env["OPENAI_API_KEY"]) {
    env["OPENAI_API_KEY"] = process.env["OPENAI_API_KEY"];
  }
  if (process.env["ANTHROPIC_API_KEY"]) {
    env["ANTHROPIC_API_KEY"] = process.env["ANTHROPIC_API_KEY"];
  }

  return { command: binary, args, env };
}

// ---------------------------------------------------------------------------
// SIGTERM → grace → SIGKILL teardown.
// Phase 60 contract: FIRST signal is ALWAYS SIGTERM, NEVER SIGINT.
// GRACE TIMING (mirror conftest.py EXACTLY):
//   SERVER teardown (agent-brain-serve): graceMs = 10000
//     (conftest.py start_seeded_server: proc.wait(timeout=10))
//   MCP-child / lighter path: graceMs = 5000
//     (conftest.py _HTTP_LISTENER_GRACE_S = 5.0)
// ---------------------------------------------------------------------------

/**
 * Gracefully terminate a child process.
 *
 * Protocol: SIGTERM → wait graceMs → SIGKILL if still alive.
 * FIRST signal is ALWAYS SIGTERM (Phase 60 contract — SIGINT is intentionally
 * NOT used for teardown; it would only appear in an explanatory comment).
 *
 * Grace timings (pass explicitly at call sites):
 *   - agent-brain-serve SERVER teardown: graceMs = 10000
 *   - agent-brain-mcp MCP-child path:    graceMs = 5000
 *
 * @param child   - The ChildProcess to terminate.
 * @param graceMs - Grace period in milliseconds before SIGKILL escalation.
 */
export function terminate(child: ChildProcess, graceMs: number): Promise<void> {
  return new Promise<void>((resolve) => {
    if (child.exitCode !== null || child.killed) {
      resolve();
      return;
    }

    // First signal: SIGTERM (Phase 60 contract — NOT SIGINT).
    child.kill("SIGTERM");

    const deadline = Date.now() + graceMs;
    const poll = setInterval(() => {
      if (child.exitCode !== null || child.killed) {
        clearInterval(poll);
        resolve();
        return;
      }
      if (Date.now() >= deadline) {
        clearInterval(poll);
        // Escalate to SIGKILL — process did not exit within grace period.
        child.kill("SIGKILL");
        // Wait for the kill to take effect.
        const waitKill = setInterval(() => {
          if (child.exitCode !== null || child.killed) {
            clearInterval(waitKill);
            resolve();
          }
        }, 50);
      }
    }, 100);
  });
}

// ---------------------------------------------------------------------------
// Stray MCP subprocess cleanup — mirrors conftest.py:_kill_stray_mcp_subprocesses()
// ---------------------------------------------------------------------------

/**
 * Best-effort cleanup of zombie agent-brain-mcp subprocesses.
 * Runs pkill -f agent-brain-mcp (ignores failure / missing pkill).
 */
export async function killStrayMcp(): Promise<void> {
  return new Promise<void>((resolve) => {
    try {
      const proc = spawn("pkill", ["-f", "agent-brain-mcp"], {
        stdio: "ignore",
      });
      const timer = setTimeout(() => {
        proc.kill("SIGKILL");
        resolve();
      }, 5000);
      proc.on("close", () => {
        clearTimeout(timer);
        resolve();
      });
      proc.on("error", () => {
        clearTimeout(timer);
        resolve(); // pkill missing or failed — ignore
      });
    } catch {
      resolve(); // best-effort
    }
  });
}

// ---------------------------------------------------------------------------
// Health polling — mirrors conftest.py:_poll_health()
// ---------------------------------------------------------------------------

interface HealthStatus {
  indexing_in_progress?: boolean;
  total_documents?: number;
  [key: string]: unknown;
}

async function _pollHealth(
  baseUrl: string,
  deadlineMs: number,
  options: { requireIdleAfterIndex?: boolean } = {}
): Promise<HealthStatus | null> {
  while (Date.now() < deadlineMs) {
    try {
      const response = await fetch(`${baseUrl}/health/status`, {
        signal: AbortSignal.timeout(2000),
      });
      if (response.ok) {
        const data = (await response.json()) as HealthStatus;
        if (options.requireIdleAfterIndex) {
          if (!data.indexing_in_progress && (data.total_documents ?? 0) > 0) {
            return data;
          }
        } else {
          return data;
        }
      }
    } catch {
      // Not yet reachable — keep polling.
    }
    await new Promise<void>((r) => setTimeout(r, HEALTH_POLL_INTERVAL_MS));
  }
  return null;
}

// ---------------------------------------------------------------------------
// Seeded-server launcher — mirrors conftest.py:start_seeded_server() VERBATIM.
// ---------------------------------------------------------------------------

export interface SeededServer {
  stateDir: string;
  proc: ChildProcess;
}

/**
 * Spin up agent-brain-serve over UDS, seed corpus, return {stateDir, proc}.
 *
 * Mirrors conftest.py:start_seeded_server() — do NOT model this on
 * agent-brain-mcp/tests/e2e/conftest.py (which has an unimplemented stub).
 *
 * Flow:
 *   1. mkdir stateDir/.agent-brain + stateDir/corpus; write 4 corpus files.
 *   2. Find free port; spawn agent-brain-serve with UDS env.
 *   3. Poll GET /health/status until reachable (deadline ~60s).
 *   4. POST /index/ {folder_path: corpus, force:false, recursive:true}.
 *   5. Poll /health/status until indexing_in_progress===false && total_documents>0
 *      (deadline ~180s).
 *
 * Teardown: call terminate(proc, 10000) then killStrayMcp() — caller's
 * responsibility (done by globalSetup teardown).
 *
 * @param stateDir - Clean temp directory; .agent-brain/ created inside.
 */
export async function startSeededServer(stateDir: string): Promise<SeededServer> {
  const projectStateDir = join(stateDir, ".agent-brain");
  const corpusDir = join(stateDir, "corpus");

  mkdirSync(projectStateDir, { recursive: true });
  mkdirSync(corpusDir, { recursive: true });

  // Write the 4 FRAMEWORK_CORPUS files.
  for (const [rel, content] of Object.entries(FRAMEWORK_CORPUS)) {
    writeFileSync(join(corpusDir, rel), content, "utf-8");
  }

  const port = await findFreePort();
  const socketPath = join(projectStateDir, "agent-brain.sock");

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    AGENT_BRAIN_STATE_DIR: projectStateDir,
    AGENT_BRAIN_UDS: "1",
    AGENT_BRAIN_UDS_PATH: socketPath,
    API_PORT: String(port),
    API_HOST: "127.0.0.1",
  };

  const proc = spawn("agent-brain-serve", [], {
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  const baseUrl = `http://127.0.0.1:${port}`;

  try {
    // Step 3: Poll until ready (deadline ~60s).
    const startupDeadline = Date.now() + SERVER_STARTUP_TIMEOUT_MS;
    const ready = await _pollHealth(baseUrl, startupDeadline);
    if (ready === null) {
      throw new Error(
        `agent-brain-serve did not become ready within ${SERVER_STARTUP_TIMEOUT_MS / 1000}s.`
      );
    }

    // Step 4: Trigger indexing.
    const indexResponse = await fetch(`${baseUrl}/index/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        folder_path: corpusDir,
        force: false,
        recursive: true,
      }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!indexResponse.ok) {
      const body = await indexResponse.text();
      throw new Error(
        `POST /index/ failed: ${indexResponse.status} ${body.slice(0, 1000)}`
      );
    }

    // Step 5: Wait for indexing to complete (deadline ~180s).
    const indexDeadline = Date.now() + INDEXING_TIMEOUT_MS;
    const indexed = await _pollHealth(baseUrl, indexDeadline, {
      requireIdleAfterIndex: true,
    });
    if (indexed === null) {
      throw new Error(
        `indexing did not complete within ${INDEXING_TIMEOUT_MS / 1000}s`
      );
    }
  } catch (err) {
    // Tear down on startup failure (10s SERVER grace).
    await terminate(proc, 10000);
    throw err;
  }

  return { stateDir, proc };
}
