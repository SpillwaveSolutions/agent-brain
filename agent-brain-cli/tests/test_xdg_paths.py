"""Tests for XDG path resolution and migration helpers."""

import os
from pathlib import Path
from unittest.mock import patch


class TestGetXdgConfigDir:
    """Tests for get_xdg_config_dir()."""

    def test_default_path(self, tmp_path: Path) -> None:
        """Returns ~/.config/agent-brain when XDG_CONFIG_HOME is not set."""
        from agent_brain_cli.xdg_paths import get_xdg_config_dir

        with patch.dict(os.environ, {}, clear=False):
            env = {k: v for k, v in os.environ.items() if k != "XDG_CONFIG_HOME"}
            with patch.dict(os.environ, env, clear=True):
                with patch("pathlib.Path.home", return_value=tmp_path):
                    result = get_xdg_config_dir()
                    assert result == tmp_path / ".config" / "agent-brain"

    def test_xdg_config_home_override(self, tmp_path: Path) -> None:
        """Returns $XDG_CONFIG_HOME/agent-brain when env var is set."""
        from agent_brain_cli.xdg_paths import get_xdg_config_dir

        custom_dir = str(tmp_path / "custom_config")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_dir}):
            result = get_xdg_config_dir()
            assert result == Path(custom_dir) / "agent-brain"


class TestGetXdgStateDir:
    """Tests for get_xdg_state_dir()."""

    def test_default_path(self, tmp_path: Path) -> None:
        """Returns ~/.local/state/agent-brain when XDG_STATE_HOME is not set."""
        from agent_brain_cli.xdg_paths import get_xdg_state_dir

        env = {k: v for k, v in os.environ.items() if k != "XDG_STATE_HOME"}
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                result = get_xdg_state_dir()
                assert result == tmp_path / ".local" / "state" / "agent-brain"

    def test_xdg_state_home_override(self, tmp_path: Path) -> None:
        """Returns $XDG_STATE_HOME/agent-brain when env var is set."""
        from agent_brain_cli.xdg_paths import get_xdg_state_dir

        custom_dir = str(tmp_path / "custom_state")
        with patch.dict(os.environ, {"XDG_STATE_HOME": custom_dir}):
            result = get_xdg_state_dir()
            assert result == Path(custom_dir) / "agent-brain"


class TestGetRegistryPath:
    """Tests for get_registry_path()."""

    def test_returns_xdg_path_when_exists(self, tmp_path: Path) -> None:
        """Returns XDG state dir registry.json when it exists there."""
        from agent_brain_cli.xdg_paths import get_registry_path

        xdg_state = tmp_path / ".local" / "state" / "agent-brain"
        xdg_state.mkdir(parents=True)
        (xdg_state / "registry.json").write_text("{}")

        legacy_dir = tmp_path / ".agent-brain"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "registry.json").write_text("{}")

        with patch.dict(os.environ, {}, clear=False):
            env = {k: v for k, v in os.environ.items() if k != "XDG_STATE_HOME"}
            with patch.dict(os.environ, env, clear=True):
                with patch("pathlib.Path.home", return_value=tmp_path):
                    result = get_registry_path()
                    assert result == xdg_state / "registry.json"

    def test_falls_back_to_legacy_when_only_legacy_exists(self, tmp_path: Path) -> None:
        """Falls back to legacy path if registry.json exists only there."""
        from agent_brain_cli.xdg_paths import get_registry_path

        legacy_dir = tmp_path / ".agent-brain"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "registry.json").write_text("{}")

        env = {k: v for k, v in os.environ.items() if k != "XDG_STATE_HOME"}
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                result = get_registry_path()
                assert result == legacy_dir / "registry.json"

    def test_returns_xdg_default_when_neither_exists(self, tmp_path: Path) -> None:
        """Returns XDG path as default write target when neither exists."""
        from agent_brain_cli.xdg_paths import get_registry_path

        env = {k: v for k, v in os.environ.items() if k != "XDG_STATE_HOME"}
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                result = get_registry_path()
                assert result == (
                    tmp_path / ".local" / "state" / "agent-brain" / "registry.json"
                )


class TestMigrateLegacyPaths:
    """Tests for migrate_legacy_paths()."""

    def test_no_legacy_dir_returns_false(self, tmp_path: Path) -> None:
        """Returns False and does nothing when no legacy dir exists."""
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                result = migrate_legacy_paths(silent=True)
                assert result is False

    def test_skips_if_xdg_dirs_already_exist(self, tmp_path: Path) -> None:
        """Returns False when XDG dirs already exist (no double-migrate)."""
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        # Create legacy dir
        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()
        (legacy / "config.yaml").write_text("test: true")

        # Create XDG config dir (already migrated)
        xdg_config = tmp_path / ".config" / "agent-brain"
        xdg_config.mkdir(parents=True)

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                result = migrate_legacy_paths(silent=True)
                assert result is False
                # Legacy dir should still exist (not deleted)
                assert legacy.exists()

    def test_migration_copies_and_deletes_legacy(self, tmp_path: Path) -> None:
        """Copies config files to XDG dirs and deletes legacy dir."""
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        # Create legacy dir with files
        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()
        (legacy / "config.yaml").write_text("embedding:\n  provider: openai\n")
        (legacy / "registry.json").write_text('{"project": "test"}')

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                result = migrate_legacy_paths(silent=True)
                assert result is True

                # Check XDG config dir has config.yaml
                xdg_config = tmp_path / ".config" / "agent-brain"
                assert (xdg_config / "config.yaml").exists()
                assert (
                    xdg_config / "config.yaml"
                ).read_text() == "embedding:\n  provider: openai\n"

                # Check XDG state dir has registry.json
                xdg_state = tmp_path / ".local" / "state" / "agent-brain"
                assert (xdg_state / "registry.json").exists()
                assert (
                    xdg_state / "registry.json"
                ).read_text() == '{"project": "test"}'

                # Legacy dir deleted
                assert not legacy.exists()

    def test_migration_handles_missing_files_gracefully(self, tmp_path: Path) -> None:
        """Migration works even if config.yaml or registry.json absent in legacy."""
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        # Create legacy dir without files
        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                result = migrate_legacy_paths(silent=True)
                assert result is True
                # Legacy dir deleted
                assert not legacy.exists()

    def test_migration_prints_notice_to_stderr(self, tmp_path: Path) -> None:
        """Prints migration notice to stderr on success."""
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        # Create legacy dir
        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()

        captured_output: list[str] = []

        def capture_echo(
            message: str = "",
            file: object = None,
            nl: bool = True,
            err: bool = False,
            color: object = None,
        ) -> None:
            if err:
                captured_output.append(str(message))

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                with patch(
                    "agent_brain_cli.xdg_paths.click.echo", side_effect=capture_echo
                ):
                    result = migrate_legacy_paths(silent=False)

        assert result is True
        assert any("migrat" in s.lower() for s in captured_output)

    def test_migration_silent_suppresses_notice(self, tmp_path: Path) -> None:
        """silent=True suppresses migration notice."""
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()

        captured_output: list[str] = []

        def capture_echo(
            message: str = "",
            file: object = None,
            nl: bool = True,
            err: bool = False,
            color: object = None,
        ) -> None:
            if err:
                captured_output.append(str(message))

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                with patch(
                    "agent_brain_cli.xdg_paths.click.echo", side_effect=capture_echo
                ):
                    result = migrate_legacy_paths(silent=True)

        assert result is True
        # No stderr output when silent=True
        assert len(captured_output) == 0

    def test_migration_catches_permission_error(self, tmp_path: Path) -> None:
        """Catches PermissionError, warns to stderr, returns False."""
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()
        (legacy / "config.yaml").write_text("test: true")

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("XDG_CONFIG_HOME", "XDG_STATE_HOME")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("pathlib.Path.home", return_value=tmp_path):
                with patch("shutil.rmtree", side_effect=PermissionError("no access")):
                    # Migration may partially complete before rmtree fails
                    result = migrate_legacy_paths(silent=True)
                    # Returns False on permission error
                    assert result is False


class TestLegacyDirConstant:
    """Tests for LEGACY_DIR constant."""

    def test_legacy_dir_is_agent_brain_in_home(self) -> None:
        """LEGACY_DIR is Path.home() / '.agent-brain'."""
        from agent_brain_cli.xdg_paths import LEGACY_DIR

        assert LEGACY_DIR == Path.home() / ".agent-brain"
