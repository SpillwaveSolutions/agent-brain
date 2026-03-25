"""Tool name mapping tables for each runtime.

Claude Code uses PascalCase tool names. Other runtimes have different
conventions. These maps translate canonical (Claude) tool names to
each runtime's native names.
"""

# Claude Code — identity mapping (canonical is already Claude format)
CLAUDE_TOOLS: dict[str, str] = {
    "Bash": "Bash",
    "Read": "Read",
    "Write": "Write",
    "Edit": "Edit",
    "Glob": "Glob",
    "Grep": "Grep",
    "Agent": "Agent",
    "WebFetch": "WebFetch",
    "WebSearch": "WebSearch",
    "NotebookEdit": "NotebookEdit",
}

# OpenCode — lowercase tool names
OPENCODE_TOOLS: dict[str, str] = {
    "Bash": "bash",
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "Glob": "glob",
    "Grep": "grep",
    "Agent": "agent",
    "WebFetch": "web_fetch",
    "WebSearch": "web_search",
    "NotebookEdit": "notebook_edit",
    "AskUserQuestion": "question",
    "SkillTool": "skill",
    "TodoWrite": "todowrite",
}

# Gemini CLI — different tool name convention
GEMINI_TOOLS: dict[str, str] = {
    "Bash": "run_shell_command",
    "Read": "read_file",
    "Write": "write_file",
    "Edit": "replace",
    "Glob": "glob",
    "Grep": "grep",
    "Agent": "agent",
    "WebFetch": "web_fetch",
    "WebSearch": "web_search",
    "NotebookEdit": "notebook_edit",
}

# Mapping from RuntimeType to tool map
TOOL_MAPS: dict[str, dict[str, str]] = {
    "claude": CLAUDE_TOOLS,
    "opencode": OPENCODE_TOOLS,
    "gemini": GEMINI_TOOLS,
}


def map_tool_name(tool: str, runtime: str) -> str:
    """Map a canonical (Claude) tool name to a runtime-specific name.

    Strips path scope annotations before looking up (e.g., "Write(.agent-brain/**)"
    becomes "Write"). Passes mcp__ prefixed tool names through unchanged.
    Falls back to lowercased base name for unknown tools.

    Args:
        tool: Canonical tool name (e.g., "Bash", "Write(.agent-brain/**)").
        runtime: Target runtime ("claude", "opencode", "gemini").

    Returns:
        Mapped tool name, or the lowercased base name if no mapping exists.
    """
    # Strip path scope annotation: "Write(.agent-brain/**)" -> "Write"
    base = tool.split("(")[0]
    tool_map = TOOL_MAPS.get(runtime, CLAUDE_TOOLS)
    mapped = tool_map.get(base)
    if mapped:
        return mapped
    # Pass MCP tools through unchanged
    if base.startswith("mcp__"):
        return base
    # Default: lowercase the base name
    return base.lower()


def map_tools(tools: list[str], runtime: str) -> list[str]:
    """Map a list of canonical tool names to runtime-specific names.

    Args:
        tools: List of canonical tool names.
        runtime: Target runtime.

    Returns:
        List of mapped tool names.
    """
    return [map_tool_name(t, runtime) for t in tools]
