# Inventory service

A three-layer inventory service used as the fixture for the Agent Brain
integration test. See `docs/architecture.md` for the design and
`docs/runbook.md` for operations.

Copy `config.ollama.yaml` to `.agent-brain/config.yaml` for a keyless run on Ollama. The Agent Brain integration test indexes this folder, then runs queries that
target one fact in each file. The expected hits are listed in
`docs/plans/2026-09-19-v10.7.0-integration-test-report.md` at the repo root.
