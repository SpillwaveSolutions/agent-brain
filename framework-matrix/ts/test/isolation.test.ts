/**
 * Isolation invariant test — proves the TypeScript suite is invisible to
 * `task before-push` (Python gate) and every pytest collection.
 *
 * This is the TS analogue of Phase 61's framework marker absence check.
 * It fails loudly if a future edit accidentally wires the TS suite into
 * the Python before-push chain.
 *
 * Uses node:fs + node:path to read the 4 package pyproject.toml files +
 * root Taskfile.yml from the repo root and asserts none contains the
 * substring "framework-matrix/ts".
 *
 * Repo root is resolved by walking up from import.meta.url to the directory
 * containing Taskfile.yml.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Resolve repo root (walk up from this file until Taskfile.yml is found).
// ---------------------------------------------------------------------------

function findRepoRoot(startDir: string): string {
  let dir = startDir;
  for (let i = 0; i < 20; i++) {
    if (existsSync(join(dir, "Taskfile.yml"))) {
      return dir;
    }
    const parent = resolve(dir, "..");
    if (parent === dir) break; // reached filesystem root
    dir = parent;
  }
  throw new Error(
    `Could not find repo root (Taskfile.yml not found starting from ${startDir})`
  );
}

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = findRepoRoot(__dirname);

// ---------------------------------------------------------------------------
// Files to check.
// ---------------------------------------------------------------------------

const PYPROJECT_PATHS = [
  join(REPO_ROOT, "agent-brain-server", "pyproject.toml"),
  join(REPO_ROOT, "agent-brain-cli", "pyproject.toml"),
  join(REPO_ROOT, "agent-brain-uds", "pyproject.toml"),
  join(REPO_ROOT, "agent-brain-mcp", "pyproject.toml"),
];

const TASKFILE_PATH = join(REPO_ROOT, "Taskfile.yml");

const FORBIDDEN_SUBSTRING = "framework-matrix/ts";

// ---------------------------------------------------------------------------
// Isolation assertions.
// ---------------------------------------------------------------------------

describe("opt-in isolation invariant", () => {
  for (const filePath of PYPROJECT_PATHS) {
    it(`${filePath} does not contain "${FORBIDDEN_SUBSTRING}"`, () => {
      const content = readFileSync(filePath, "utf-8");
      expect(content).not.toContain(FORBIDDEN_SUBSTRING);
    });
  }

  it(`root Taskfile.yml does not contain "${FORBIDDEN_SUBSTRING}"`, () => {
    const content = readFileSync(TASKFILE_PATH, "utf-8");
    expect(content).not.toContain(FORBIDDEN_SUBSTRING);
  });

  it("root Taskfile.yml before-push chain has no pnpm or vitest step", () => {
    const content = readFileSync(TASKFILE_PATH, "utf-8");
    // Verify no pnpm or vitest invocation is in the Taskfile
    expect(content).not.toMatch(/\bpnpm\b/);
    expect(content).not.toMatch(/\bvitest\b/);
  });

  it("each pyproject.toml testpaths points only to 'tests' (not framework-matrix)", () => {
    for (const filePath of PYPROJECT_PATHS) {
      const content = readFileSync(filePath, "utf-8");
      // If the file has a testpaths setting, it should not include framework-matrix
      if (content.includes("testpaths")) {
        expect(content).not.toContain("framework-matrix");
      }
    }
  });

  it("repo root is correctly resolved (Taskfile.yml exists)", () => {
    expect(existsSync(TASKFILE_PATH)).toBe(true);
  });
});
