"""Cursor runtime converter.

Cursor consumes the same commands/skills layout as Claude Code, plus a
``.cursor-plugin/plugin.json`` that points at those directories. Grok-style
Agent Plugins 1.0 files (``plugin.json``, ``mcp.json``) are copied through
when present so a Cursor install is also a valid universal plugin.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from agent_brain_cli.runtime.claude_converter import ClaudeConverter
from agent_brain_cli.runtime.types import PluginBundle, RuntimeType, Scope


def _copy_rel(source: Path, target: Path, rel: str, created: list[Path]) -> None:
    src = source / rel
    if not src.is_file():
        return
    dest = target / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    created.append(dest)


class CursorConverter(ClaudeConverter):
    """Converter for Cursor (Claude layout + Cursor/universal manifests)."""

    @property
    def runtime_type(self) -> RuntimeType:
        return RuntimeType.CURSOR

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        created = super().install(bundle, target_dir, scope)
        source = Path(bundle.source_dir)
        for rel in (
            ".cursor-plugin/plugin.json",
            "plugin.json",
            "mcp.json",
        ):
            _copy_rel(source, target_dir, rel, created)
        return created
