/**
 * Per-framework / per-stage failure fingerprint wrapper.
 *
 * Success Criterion 4 (Phase 62): failures must surface
 *   `[<framework>] <stage> failed: ...`
 * NOT an opaque Node stack trace.
 *
 * Port of Phase 61 Python convention — each smoke-flow stage is wrapped so
 * a thrown error names the framework and the stage rather than leaking raw
 * internal stack traces to the test output.
 *
 * Stages (exhaustive union — all must appear here so both test files can
 * route their full flow through this wrapper and still typecheck under
 * `pnpm exec tsc --noEmit` in strict mode):
 *   connect     — client construction + connect call
 *   list-tools  — fetching available tool set
 *   call        — invoking the target tool
 *   assert      — assertNonEmptySearch result validation
 *   disconnect  — teardown (close / disconnect)
 */

export type Stage = "connect" | "list-tools" | "call" | "assert" | "disconnect";

/**
 * Wrap a smoke-flow stage so a thrown error names the framework and stage.
 *
 * On success: returns the resolved value of fn().
 * On throw:   rethrows a new Error whose message is
 *               `[${framework}] ${stage} failed: ${original.message}`
 *             with `.cause` set to the original error (preserves the stack
 *             for debugging while leading with the clean fingerprint line).
 *
 * @param framework - Framework label, e.g. `"mastra"` or `"vercel-ai-sdk"`.
 * @param stage     - One of the Stage union literals (see above).
 * @param fn        - The async or sync action to execute.
 * @returns The resolved value of fn().
 * @throws Error with `[framework] stage failed: ...` prefix on any thrown value.
 *
 * @example
 * await stage("mastra", "connect", () => client.connect());
 * await stage("mastra", "disconnect", () => client.disconnect());
 */
export async function stage<T>(
  framework: string,
  stageLabel: Stage,
  fn: () => Promise<T> | T,
): Promise<T> {
  try {
    return await fn();
  } catch (err) {
    const originalMessage =
      err instanceof Error ? err.message : String(err);
    const wrapped = new Error(
      `[${framework}] ${stageLabel} failed: ${originalMessage}`,
    );
    (wrapped as Error & { cause?: unknown }).cause = err;
    throw wrapped;
  }
}
