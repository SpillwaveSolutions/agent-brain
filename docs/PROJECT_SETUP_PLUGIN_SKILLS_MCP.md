# Set up Agent Brain in a project: Plugin + Skills + MCP

Step-by-step instructions to wire Agent Brain into a single project directory using the
**Claude Code plugin** (slash commands + skills) **and** the **MCP server** (so the model can call
Agent Brain as tools). All three layers share one `.agent-brain/` backend.

> Want only the MCP server, no plugin? See the [MCP Quickstart](./MCP_QUICKSTART.md). Want the full
> command reference? See the [Plugin Guide](./PLUGIN_GUIDE.md) and [MCP User Guide](./MCP_USER_GUIDE.md).

---

## The three layers (and how they relate)

| Layer | What it is | Who drives it | Installed by |
|-------|-----------|---------------|--------------|
| **Plugin** | 30 `/agent-brain-*` slash commands + 3 agents | You, by typing commands | `claude plugins install …` |
| **Skills** | `configuring-agent-brain` + `using-agent-brain` — context-aware help | Triggered by your natural language | bundled **with the plugin** |
| **MCP server** | 16 tools / 5 resources / 6 prompts over MCP | The **model**, autonomously | `install-agent --with-mcp` (or manual `.mcp.json`) |

They don't conflict — run all three against the same backend.

---

## Prerequisites

- **Python 3.10+** and **Claude Code**
- An embeddings provider key (e.g. `OPENAI_API_KEY`) — or Ollama for fully-local
- A project directory you want to make searchable

---

## Step 1 — Install the plugin (commands + agents + skills)

In Claude Code:

```
claude plugins install github:SpillwaveSolutions/agent-brain
```

This installs **30 slash commands**, **3 agents**, and the **2 skills**
(`agent-brain:configuring-agent-brain`, `agent-brain:using-agent-brain`). The skills come bundled —
no separate skill install for Claude Code.

Verify the plugin loaded:

```
/agent-brain-help
```

You should see the Agent Brain command list. (Skills don't need manual enabling — they activate
automatically when your request matches their triggers; see Step 5.)

---

## Step 2 — Set up the project (guided wizard)

From the project directory, run the wizard — it uses the `configuring-agent-brain` skill:

```
/agent-brain-setup
```

It walks you through: installing packages (`agent-brain-rag`, `agent-brain-cli`), choosing
embedding/summarization providers + keys, picking a storage backend, initializing `.agent-brain/`,
starting the server, and indexing. It also offers the **MCP registration** in its final step.

Prefer to do it by hand? The equivalent commands:

```
/agent-brain-install      # install packages (asks pipx / uv / pip / conda)
/agent-brain-providers    # configure embedding + summarization keys
/agent-brain-init         # create .agent-brain/ in this project
/agent-brain-start        # start the backend
/agent-brain-index .      # index the project (or a subdir like ./docs ./src)
/agent-brain-status       # expect: healthy, document count > 0
```

> The CLI works too if you're in a terminal: `agent-brain init && agent-brain start && agent-brain index ./docs`.

---

## Step 3 — Register the MCP server

This is the step that lets the **model** call Agent Brain as tools (separate from the slash
commands). From the project directory in a terminal:

```bash
# Install the MCP package if needed
pip install agent-brain-ag-mcp

# Register the server for Claude Code (writes/merges .mcp.json; preview with --dry-run)
agent-brain install-agent --agent claude --with-mcp --dry-run
agent-brain install-agent --agent claude --with-mcp
```

This merges an `agent-brain` entry into the project's `.mcp.json`, preserving any other servers and
pinning an absolute `AGENT_BRAIN_STATE_DIR`. It's idempotent. Confirm:

```bash
cat .mcp.json
```

**Alternative (manual):** add the same block yourself, or for a remote OAuth-protected server add
`--mcp-auth oauth`. See [MCP User Guide → Authentication](./MCP_USER_GUIDE.md#authentication).

Now **reload Claude Code** in this project. It reads `.mcp.json` on startup and prompts you to
**approve** the `agent-brain` server — approve it, and the 16 tools become available to the model.

---

## Step 4 — Verify all three layers

```bash
# Plugin (slash command)
/agent-brain-status                                   # healthy + doc count

# MCP server, end-to-end via the CLI's MCP transport
agent-brain --transport mcp resources read corpus://status
```

- **Skills:** in a Claude Code message, say *"configure agent brain"* or *"search the docs for X"* —
  the relevant skill (`configuring-agent-brain` / `using-agent-brain`) should activate.
- **MCP tools:** ask the model *"use agent-brain to search the corpus for …"* — it should call the
  `search_documents` tool itself (you'll see the tool invocation).

---

## Step 5 — Use it (three ways)

You now have three complementary entry points to the same indexed corpus:

1. **Slash commands (you drive):**
   ```
   /agent-brain-search "how is authentication handled" --mode hybrid
   /agent-brain-graph "what calls register_claude_mcp"
   /agent-brain-index ./new-folder
   ```
2. **Skills (natural language, auto-triggered):**
   > "Search the knowledge base for the retry logic."
   > "Help me configure Agent Brain to use Ollama."
   The `using-agent-brain` / `configuring-agent-brain` skill activates and guides the work.
3. **MCP tools (model-driven, autonomous):** during normal agentic work the model picks
   `search_documents`, reads `corpus://status`, or expands a prompt like `onboard-to-codebase`
   without you naming a tool.

**Rule of thumb:** slash commands for deliberate, scripted actions; skills for guided help; MCP for
letting the agent retrieve context on its own mid-task.

---

## What's in the project after setup

```
your-project/
├── .agent-brain/            # backend state: index, config, runtime.json, UDS socket
│   └── config.yaml          # providers, storage, graphrag (chmod 600)
├── .mcp.json                # MCP server registration (Step 3)  ← model reads this
└── .claude/                 # Claude Code plugin/runtime files (if install-agent was used)
```

Keep `.agent-brain/config.yaml` and `.mcp.json` out of version control if they contain secrets or
machine-specific absolute paths.

---

## Other runtimes (OpenCode / Gemini / Codex)

The plugin and skills install for other runtimes via the CLI converter:

```bash
agent-brain install-agent --agent opencode    # or gemini / codex / skill-runtime --dir <path>
```

MCP **auto-registration** (`--with-mcp`) targets **Claude Code** and **OpenCode**
(`install-agent --agent opencode --with-mcp` writes the project-root `opencode.json`). For Gemini
and Codex, register the MCP server manually using the JSON in the
[MCP User Guide](./MCP_USER_GUIDE.md#configuration) (tracked as
[#225](https://github.com/SpillwaveSolutions/agent-brain/issues/225)–[#226](https://github.com/SpillwaveSolutions/agent-brain/issues/226)).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/agent-brain-*` commands missing | Re-run `claude plugins install …`; reload Claude Code |
| Skill doesn't trigger | Phrase the request to match its purpose ("configure…", "search the docs…"); skills are bundled with the plugin |
| MCP server not in Claude Code | Confirm `.mcp.json` exists at the project root and you approved the server after reload |
| `agent-brain-mcp: command not found` (in host) | Use the absolute path from `which agent-brain-mcp` as `command` in `.mcp.json` |
| Tools/commands return "backend unavailable" | Start the backend: `agent-brain start`, then `agent-brain status` |
| Empty results everywhere | Index something: `agent-brain index ./docs`, confirm doc count > 0 |
| Wrong corpus from MCP | `AGENT_BRAIN_STATE_DIR` points at the wrong `.agent-brain`; re-run `install-agent --with-mcp` from the right project root |

---

## Related docs

- [MCP Quickstart](./MCP_QUICKSTART.md) — MCP server only, 5-minute path
- [MCP User Guide](./MCP_USER_GUIDE.md) — full tool/resource/prompt reference, OAuth, per-host config
- [Plugin Guide](./PLUGIN_GUIDE.md) — every slash command and agent
- [User Guide](./USER_GUIDE.md) — backend setup, indexing, retrieval modes
- [Configuring Agent Brain skill](../agent-brain-plugin/skills/configuring-agent-brain/SKILL.md) — installation/config skill reference
