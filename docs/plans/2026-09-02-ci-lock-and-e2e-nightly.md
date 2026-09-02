# Plan: stop the CI `poetry lock` tax; make E2E CLI local-only until it can pass

date: 2026-09-02
status: ready-for-review
issues: [#238](https://github.com/SpillwaveSolutions/agent-brain/issues/238), [#240](https://github.com/SpillwaveSolutions/agent-brain/issues/240), [#218](https://github.com/SpillwaveSolutions/agent-brain/issues/218)

## Why

v10.5.0 publish spent **87 of 95 minutes** on two sequential cold `poetry lock`
re-resolves of torch/CUDA. The E2E CLI nightly has not run a single test in
weeks: step 8 is cancelled at the 30-minute wall (~44 min needed). The same
swap-and-re-lock is an interruption hazard that can leave `path =` pins in a
publishable `pyproject.toml`.

## Scope

1. **#240 option 1 (now).** Keep Keycloak nightly scheduled (the one signal
   still worth reading). Gate the `e2e-cli` job on `workflow_dispatch` only.
   Document `./e2e-cli/run.sh` as the supported full-suite path.
2. **#238 / #240 option 3.** Install CLI/MCP from the committed lock, then
   overlay locally-built server/uds wheels. No `sed` rewrite, no `poetry lock`.
3. **#238 trap + lock guard.** Restore `pyproject.toml` on EXIT in both
   `mcp:install` and `cli:install`. Snapshot mcp + uds locks in
   `before_push_lock_guard.sh`. Fail `before-push` if a runtime `path =` pin
   is present.
4. **#218 diagnostic + nbf.** `JwksTokenVerifier` currently `require`s `nbf`.
   RFC 7519 marks `nbf` optional; Keycloak access tokens typically omit it.
   That would reject every Keycloak JWT *regardless of aud*, which matches
   the observed 3-pass (introspection / kid, no `nbf` check) / 4-fail (JWKS
   path) split. Honor `nbf` when present; do not require it. Dump unverified
   claims in the Keycloak JWT assertion so the next CI run still settles aud
   with evidence, not inference.

## Out of scope

- Raising the nightly timeout as a substitute for (2).
- Re-enabling the E2E CLI schedule before a dispatch run actually executes
  tests.
- Guessing an audience-mapper fix without a decoded token.
