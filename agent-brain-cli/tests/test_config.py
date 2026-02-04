"""Tests for CLI configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

from agent_brain_cli.config import (
    AgentBrainConfig,
    EmbeddingConfig,
    ProjectConfig,
    ServerConfig,
    SummarizationConfig,
    get_server_url,
    get_state_dir,
    load_config,
)


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ServerConfig()
        assert config.url == "http://127.0.0.1:8000"
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.auto_port is True


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ProjectConfig()
        assert config.state_dir is None
        assert config.project_root is None

    def test_custom_state_dir(self) -> None:
        """Test custom state directory."""
        config = ProjectConfig(state_dir="/custom/path")
        assert config.state_dir == "/custom/path"


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = EmbeddingConfig()
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-large"
        assert config.api_key_env == "OPENAI_API_KEY"
        assert config.api_key is None

    def test_direct_api_key(self) -> None:
        """Test direct API key configuration."""
        config = EmbeddingConfig(api_key="test-key")
        assert config.api_key == "test-key"


class TestSummarizationConfig:
    """Tests for SummarizationConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SummarizationConfig()
        assert config.provider == "anthropic"
        assert config.model == "claude-haiku-4-5-20251001"
        assert config.api_key_env == "ANTHROPIC_API_KEY"


class TestAgentBrainConfig:
    """Tests for AgentBrainConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AgentBrainConfig()
        assert config.server.url == "http://127.0.0.1:8000"
        assert config.project.state_dir is None
        assert config.embedding.provider == "openai"
        assert config.summarization.provider == "anthropic"

    def test_from_dict(self) -> None:
        """Test creating config from dictionary (as from YAML)."""
        config = AgentBrainConfig(
            server={"url": "http://localhost:9000", "port": 9000},
            project={"state_dir": "/custom/state"},
            embedding={"provider": "ollama", "model": "nomic-embed-text"},
        )
        assert config.server.url == "http://localhost:9000"
        assert config.server.port == 9000
        assert config.project.state_dir == "/custom/state"
        assert config.embedding.provider == "ollama"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_default_when_no_config(self) -> None:
        """Test defaults are used when no config file exists."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "agent_brain_cli.config._find_config_file",
                return_value=None,
            ),
        ):
            config = load_config(Path("/nonexistent"))
            assert config.server.url == "http://127.0.0.1:8000"
            assert config.embedding.provider == "openai"

    def test_env_var_override(self) -> None:
        """Test environment variable overrides config file."""
        with patch.dict(
            os.environ,
            {"AGENT_BRAIN_URL": "http://custom:8080"},
            clear=True,
        ):
            config = load_config(Path("/nonexistent"))
            assert config.server.url == "http://custom:8080"

    def test_state_dir_env_override(self) -> None:
        """Test state dir environment variable override."""
        with patch.dict(
            os.environ,
            {"AGENT_BRAIN_STATE_DIR": "/env/state/dir"},
            clear=True,
        ):
            config = load_config(Path("/nonexistent"))
            assert config.project.state_dir == "/env/state/dir"


class TestGetServerUrl:
    """Tests for get_server_url function."""

    def test_default_url(self) -> None:
        """Test default URL when nothing configured."""
        with patch.dict(os.environ, {}, clear=True):
            url = get_server_url()
            assert url == "http://127.0.0.1:8000"

    def test_env_var_takes_precedence(self) -> None:
        """Test environment variable takes precedence."""
        with patch.dict(os.environ, {"AGENT_BRAIN_URL": "http://envvar:9000"}):
            url = get_server_url()
            assert url == "http://envvar:9000"


class TestGetStateDir:
    """Tests for get_state_dir function."""

    def test_default_state_dir(self) -> None:
        """Test default state directory path."""
        with patch.dict(os.environ, {}, clear=True):
            project_root = Path("/my/project")
            state_dir = get_state_dir(project_root=project_root)
            assert state_dir == project_root / ".claude/agent-brain"

    def test_env_var_takes_precedence(self) -> None:
        """Test environment variable takes precedence."""
        with (
            patch.dict(os.environ, {"AGENT_BRAIN_STATE_DIR": "/env/state"}),
            patch(
                "agent_brain_cli.config._find_project_root",
                return_value=Path("/fake/project"),
            ),
            patch(
                "agent_brain_cli.config._find_config_file",
                return_value=None,
            ),
        ):
            state_dir = get_state_dir(project_root=Path("/fake/project"))
            assert state_dir == Path("/env/state")

    def test_config_state_dir(self) -> None:
        """Test state dir from config object."""
        config = AgentBrainConfig(project={"state_dir": "/config/state"})
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "agent_brain_cli.config._find_project_root",
                return_value=Path("/fake/project"),
            ),
        ):
            state_dir = get_state_dir(config=config, project_root=Path("/fake/project"))
            assert state_dir == Path("/config/state")


class TestConfigFileLoading:
    """Tests for loading config from YAML files."""

    def test_load_yaml_config(self, tmp_path: Path) -> None:
        """Test loading config from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
server:
  url: "http://test:8080"
  port: 8080

project:
  state_dir: "/test/state"

embedding:
  provider: "ollama"
  model: "nomic-embed-text"
"""
        )

        # Set config path and ensure no env var overrides
        with patch.dict(
            os.environ,
            {"AGENT_BRAIN_CONFIG": str(config_file)},
            clear=False,
        ):
            # Temporarily remove any override env vars
            saved_url = os.environ.pop("AGENT_BRAIN_URL", None)
            saved_state = os.environ.pop("AGENT_BRAIN_STATE_DIR", None)
            try:
                config = load_config()
                assert config.server.url == "http://test:8080"
                assert config.server.port == 8080
                assert config.project.state_dir == "/test/state"
                assert config.embedding.provider == "ollama"
            finally:
                # Restore any removed env vars
                if saved_url:
                    os.environ["AGENT_BRAIN_URL"] = saved_url
                if saved_state:
                    os.environ["AGENT_BRAIN_STATE_DIR"] = saved_state

    def test_config_with_api_key(self, tmp_path: Path) -> None:
        """Test loading config with direct API key."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
embedding:
  provider: "openai"
  api_key: "sk-test-key"

summarization:
  provider: "anthropic"
  api_key: "sk-ant-test-key"
"""
        )

        with patch.dict(os.environ, {"AGENT_BRAIN_CONFIG": str(config_file)}):
            config = load_config()
            assert config.embedding.api_key == "sk-test-key"
            assert config.summarization.api_key == "sk-ant-test-key"

    def test_project_config_file(self, tmp_path: Path) -> None:
        """Test loading from project .claude/agent-brain/config.yaml."""
        # Create project structure
        state_dir = tmp_path / ".claude" / "agent-brain"
        state_dir.mkdir(parents=True)
        config_file = state_dir / "config.yaml"
        config_file.write_text(
            """
server:
  url: "http://project:8000"
"""
        )

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(tmp_path)
            assert config.server.url == "http://project:8000"
