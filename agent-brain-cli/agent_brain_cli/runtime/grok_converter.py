"""Grok Build runtime converter.

Grok Build loads Claude Code plugins with zero config, so the payload is the
Claude layout plus ``.grok-plugin/marketplace.json`` for native marketplace
identity. Universal Agent Plugins 1.0 files are copied through when present.
"""

from __future__ import annotations

from pathlib import Path

from agent_brain_cli.runtime.claude_converter import ClaudeConverter
from agent_brain_cli.runtime.cursor_converter import _copy_rel
from agent_brain_cli.runtime.types import PluginBundle, RuntimeType, Scope


class GrokConverter(ClaudeConverter):
    """Converter for Grok Build (Claude-compatible + Grok marketplace)."""

    @property
    def runtime_type(self) -> RuntimeType:
        return RuntimeType.GROK

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        created = super().install(bundle, target_dir, scope)
        source = Path(bundle.source_dir)
        for rel in (
            ".grok-plugin/marketplace.json",
            "plugin.json",
            "mcp.json",
        ):
            _copy_rel(source, target_dir, rel, created)
        return created
