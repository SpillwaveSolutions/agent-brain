# Agent Brain Quick Start

Get up and running with Agent Brain in minutes. The Claude Code plugin is the primary interface - once installed, it handles everything else for you.

## Step 1: Install the Plugin

Install the Agent Brain plugin in Claude Code:

```bash
claude plugins install github:SpillwaveSolutions/agent-brain
```

This gives you access to 24 commands, 3 intelligent agents, and 2 skills for working with Agent Brain.

## Step 2: Install the Server and CLI

Use the plugin to install the Python packages:

```
/agent-brain-install
```

This installs:
- `agent-brain-rag` - The FastAPI server for indexing and search
- `agent-brain-cli` - Command-line tool (used internally by the plugin)

## Step 3: Configure API Keys

Configure your embedding and summarization providers:

```
/agent-brain-providers
```

Choose from:
- **Cloud providers**: OpenAI, Anthropic, Cohere, Gemini, Grok
- **Local providers**: Ollama (fully offline mode)

Or use the complete setup wizard which handles installation AND configuration:

```
/agent-brain-setup
```

## Step 4: Initialize Your Project

Initialize Agent Brain for your current project:

```
/agent-brain-init
```

This creates a `.claude/doc-serve/` directory with project-specific configuration.

## Step 5: Start the Server

Start the Agent Brain server:

```
/agent-brain-start
```

The server starts with automatic port allocation (no conflicts with other projects).

## Step 6: Index Your Documentation

Index your project's documentation and code:

```
/agent-brain-index ./docs
```

For code + documentation:

```
/agent-brain-index . --include-code
```

Check indexing status:

```
/agent-brain-status
```

## Step 7: Search Your Knowledge Base

Now you can search! Use the smart search command:

```
/agent-brain-search "how does authentication work"
```

Or use specific search modes:

```
/agent-brain-semantic "explain the architecture"
/agent-brain-keyword "getUserById"
/agent-brain-graph "what calls AuthService"
```

---

## All-in-One Setup

For the fastest setup, use the interactive wizard which does steps 2-6 automatically:

```
/agent-brain-setup
```

The Setup Assistant guides you through:
1. Installing packages
2. Configuring API keys
3. Initializing the project
4. Starting the server
5. Indexing your documentation

---

## Search Modes Quick Reference

| Command | Best For | Example |
|---------|----------|---------|
| `/agent-brain-search` | General questions | "how does caching work" |
| `/agent-brain-semantic` | Conceptual queries | "explain the data flow" |
| `/agent-brain-keyword` | Exact terms, errors | "NullPointerException" |
| `/agent-brain-hybrid` | Fine-tuned search | "API authentication" |
| `/agent-brain-graph` | Dependencies | "what uses UserService" |
| `/agent-brain-multi` | Maximum recall | "everything about validation" |

---

## Using Agents for Complex Tasks

For complex research tasks, Agent Brain's intelligent agents help:

**You**: "Research how error handling is implemented across the codebase"

**Research Assistant** automatically:
1. Searches documentation for error handling patterns
2. Queries code for try/catch blocks and error classes
3. Uses graph mode to find error propagation
4. Synthesizes a comprehensive answer with file references

---

## Verify Your Setup

Check that everything is working:

```
/agent-brain-verify
```

This validates:
- Package installation
- API key configuration
- Server connectivity
- Index health

---

## Next Steps

- [User Guide](USER_GUIDE.md) - Detailed usage patterns
- [Plugin Guide](PLUGIN_GUIDE.md) - All 24 commands documented
- [Provider Configuration](../agent-brain-plugin/skills/using-agent-brain/references/provider-configuration.md) - Configure embedding and summarization providers
