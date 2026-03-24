"""Regression test for BUGFIX-01: start command timeout default is 120 seconds.

BUGFIX-01: Increase agent-brain start timeout default to 120 seconds to support
first-run sentence-transformers initialization.
"""

import pytest


def test_start_command_timeout_default_is_120() -> None:
    """BUGFIX-01: Start timeout must default to 120s for sentence-transformers init."""
    from agent_brain_cli.commands.start import start_command

    for param in start_command.params:
        if param.name == "timeout":
            assert param.default == 120, (
                f"BUGFIX-01: --timeout default must be 120s for sentence-transformers "
                f"first-run init, got: {param.default}"
            )
            return
    pytest.fail("--timeout parameter not found on start_command")


def test_start_command_timeout_param_exists() -> None:
    """BUGFIX-01: start_command must have a --timeout parameter."""
    from agent_brain_cli.commands.start import start_command

    param_names = [p.name for p in start_command.params]
    assert (
        "timeout" in param_names
    ), f"start_command must have a --timeout parameter, found: {param_names}"


def test_start_command_timeout_help_mentions_default() -> None:
    """BUGFIX-01: --timeout help text should mention the default value."""
    from agent_brain_cli.commands.start import start_command

    for param in start_command.params:
        if param.name == "timeout":
            # Help text should mention the default
            assert param.help is not None, "--timeout must have a help string"
            assert "120" in (
                param.help or ""
            ), f"--timeout help should mention 120s default, got: {param.help}"
            return
    pytest.fail("--timeout parameter not found on start_command")
