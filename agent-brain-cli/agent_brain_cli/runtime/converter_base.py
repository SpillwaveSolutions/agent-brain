"""Base protocol for runtime converters."""

from pathlib import Path
from typing import Protocol

from agent_brain_cli.runtime.types import (
    PluginAgent,
    PluginBundle,
    PluginCommand,
    PluginSkill,
    RuntimeType,
    Scope,
)


class RuntimeConverter(Protocol):
    """Protocol that each runtime converter must implement."""

    @property
    def runtime_type(self) -> RuntimeType:
        """The runtime this converter targets."""
        ...

    def convert_command(self, command: PluginCommand) -> str:
        """Convert a command to the runtime's native format.

        Args:
            command: Parsed canonical command.

        Returns:
            String content for the output file.
        """
        ...

    def convert_agent(self, agent: PluginAgent) -> str:
        """Convert an agent to the runtime's native format.

        Args:
            agent: Parsed canonical agent.

        Returns:
            String content for the output file.
        """
        ...

    def convert_skill(self, skill: PluginSkill) -> str:
        """Convert a skill to the runtime's native format.

        Args:
            skill: Parsed canonical skill.

        Returns:
            String content for the output file.
        """
        ...

    def install(
        self,
        bundle: PluginBundle,
        target_dir: Path,
        scope: Scope,
    ) -> list[Path]:
        """Install converted plugin files to the target directory.

        Args:
            bundle: Complete parsed plugin bundle.
            target_dir: Where to write the output files.
            scope: Project-level or global installation.

        Returns:
            List of created file paths.
        """
        ...
