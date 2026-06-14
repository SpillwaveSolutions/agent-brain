/**
 * Vitest global setup — runs ONCE per `pnpm test`.
 *
 * Checks prerequisites. If ok: creates a short temp state dir (abfwm- prefix
 * to dodge the macOS 104-char AF_UNIX socket-path limit — mirrors conftest.py's
 * tempfile.mkdtemp(prefix="abfwm-")), seeds agent-brain-serve with
 * FRAMEWORK_CORPUS, and ALWAYS sets process.env.AB_FWM_STATE_DIR as the
 * MANDATORY canonical handoff to both Plan 62-02 framework tests.
 *
 * If prerequisites are missing: leaves AB_FWM_STATE_DIR UNSET and returns a
 * no-op teardown so corpus.test.ts and every framework test skips gracefully
 * (server-free on machines without OPENAI_API_KEY / binaries).
 *
 * CANONICAL HANDOFF (mandatory — Plan 62-01 requirement):
 *   process.env.AB_FWM_STATE_DIR = stateDir
 *   Both Plan 62-02 tests read process.env.AB_FWM_STATE_DIR and skip when unset.
 *   A file under the temp dir MAY exist as an optional secondary breadcrumb,
 *   but the env var IS the required contract.
 *
 * TEARDOWN: terminate(serverChild, 10000) then killStrayMcp().
 *   SERVER grace = 10000 ms to mirror conftest.py:proc.wait(timeout=10).
 *
 * Canonical sources:
 *   - framework-matrix/conftest.py:seeded_mcp_server (session-scoped fixture)
 *   - framework-matrix/_harness.py:prerequisites_available
 */

import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  prerequisitesAvailable,
  startSeededServer,
  terminate,
  killStrayMcp,
} from "./harness.js";

import type { ChildProcess } from "node:child_process";

export default async function setup(): Promise<() => Promise<void>> {
  const { ok, reason } = prerequisitesAvailable();

  if (!ok) {
    // Prerequisites missing — leave AB_FWM_STATE_DIR UNSET.
    // corpus.test.ts is server-free and will pass.
    // Both framework tests in 62-02 will skip gracefully.
    console.log(`[globalSetup] Skipping server seed: ${reason}`);
    return async () => {
      // no-op teardown
    };
  }

  // Use a short "abfwm-" prefix to dodge the macOS 104-char AF_UNIX path limit.
  // Mirrors conftest.py: state_dir = Path(tempfile.mkdtemp(prefix="abfwm-"))
  const stateDir = mkdtempSync(join(tmpdir(), "abfwm-"));

  console.log(`[globalSetup] Seeding agent-brain-serve at ${stateDir}`);
  const { proc } = await startSeededServer(stateDir);
  const serverChild: ChildProcess = proc;

  // CANONICAL HANDOFF (mandatory — not "AND/OR"): ALWAYS set the env var.
  process.env["AB_FWM_STATE_DIR"] = stateDir;
  console.log(`[globalSetup] AB_FWM_STATE_DIR=${stateDir}`);

  // Return teardown: SERVER grace = 10000 ms (mirrors conftest.py's
  // proc.wait(timeout=10)); then best-effort pkill agent-brain-mcp.
  return async () => {
    console.log("[globalSetup] Tearing down seeded server (SIGTERM, 10s grace)");
    await terminate(serverChild, 10000);
    await killStrayMcp();
    console.log("[globalSetup] Teardown complete");
  };
}
