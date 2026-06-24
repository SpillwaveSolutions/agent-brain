# Agent Brain — TODO

Repo-level pending work is now tracked in **GitHub issues**, not inline here.
Per-phase tracking lives under `.planning/todos/`.

## Where to look

- **Live backlog:** [open issues](https://github.com/SpillwaveSolutions/agent-brain/issues)
- **Roadmap survey (post-v10.4):** [`docs/plans/backlog-survey.md`](docs/plans/backlog-survey.md) —
  groups the open issues by theme and recommends the next milestone.

## Next milestone candidate

**Enterprise Hardening + Cloud Deployment (GCP-first).** Design doc:
[`docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md`](docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md).
Follow-up issues: #200–#205.

## MCP auto-registration — multi-runtime follow-ups

`install-agent --with-mcp` registers the MCP server for Claude Code (shipped in #223).
Extend the same auto-registration to the other runtimes (each has its own MCP config format):

- [ ] [#224](https://github.com/SpillwaveSolutions/agent-brain/issues/224) — OpenCode (`opencode.json` `mcp`)
- [ ] [#225](https://github.com/SpillwaveSolutions/agent-brain/issues/225) — Gemini CLI (`settings.json` `mcpServers`)
- [ ] [#226](https://github.com/SpillwaveSolutions/agent-brain/issues/226) — Codex (`config.toml` `[mcp_servers]`)

> The native MCP server (formerly tracked here as #153/#167) shipped in the v10.1–v10.4 line
> and is no longer pending. The full MCP v1–v4 roadmap is complete as of v10.4.0.
