"""Tests for config validation engine and 'agent-brain config validate' CLI command."""

import json
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.config_schema import (
    POSTGRES_KNOWN_FIELDS,
    ConfigValidationError,
    format_validation_errors,
    validate_config_dict,
    validate_config_file,
)

# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


VALID_MINIMAL_YAML = """\
embedding:
  provider: openai
  model: text-embedding-3-large
summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
"""

VALID_FULL_YAML = """\
embedding:
  provider: openai
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY
summarization:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
reranker:
  provider: sentence-transformers
  model: cross-encoder/ms-marco-MiniLM-L-6-v2
storage:
  backend: chroma
graphrag:
  enabled: true
  store_type: simple
  use_code_metadata: true
  doc_extractor: langextract
api:
  host: 127.0.0.1
  port: 8000
"""


# ---------------------------------------------------------------------------
# Tests for validate_config_file / validate_config_dict (engine)
# ---------------------------------------------------------------------------


class TestValidateConfigDict:
    """Unit tests for the dict-based validation engine."""

    def test_valid_minimal_config_returns_no_errors(self) -> None:
        """Valid minimal config returns empty error list."""
        config = yaml.safe_load(VALID_MINIMAL_YAML)
        errors = validate_config_dict(config)
        assert errors == []

    def test_valid_full_config_returns_no_errors(self) -> None:
        """Test 2: fully populated valid config returns empty list."""
        config = yaml.safe_load(VALID_FULL_YAML)
        errors = validate_config_dict(config)
        assert errors == []

    def test_invalid_embedding_provider_returns_error(self) -> None:
        """Invalid embedding.provider returns fix suggestion."""
        config = {
            "embedding": {"provider": "badprovider", "model": "some-model"},
            "summarization": {"provider": "anthropic"},
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        field_error = next((e for e in errors if e.field == "embedding.provider"), None)
        assert field_error is not None, f"No error for embedding.provider in {errors}"
        # Suggestion must mention valid providers
        assert "openai" in field_error.suggestion
        assert "ollama" in field_error.suggestion

    def test_invalid_storage_backend_returns_error(self) -> None:
        """Test 4: invalid storage.backend returns error mentioning valid options."""
        config = {
            "embedding": {"provider": "openai"},
            "summarization": {"provider": "anthropic"},
            "storage": {"backend": "sqlite"},
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        field_error = next((e for e in errors if e.field == "storage.backend"), None)
        assert field_error is not None, f"No error for storage.backend in {errors}"
        assert "chroma" in field_error.suggestion
        assert "postgres" in field_error.suggestion

    def test_unknown_top_level_key_returns_error(self) -> None:
        """Test 5: unknown top-level key 'foobar' returns error with key name."""
        config = {
            "embedding": {"provider": "openai"},
            "foobar": {"something": True},
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        unknown_error = next(
            (e for e in errors if "foobar" in e.field or "foobar" in e.message), None
        )
        assert unknown_error is not None, f"No error mentioning 'foobar' in {errors}"

    def test_unknown_sub_key_in_embedding_returns_error(self) -> None:
        """Test 6: embedding.port is unknown field — should produce an error."""
        config = {
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-large",
                "port": 8080,  # wrong — port belongs under api
            },
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        port_error = next(
            (e for e in errors if "port" in e.field or "port" in e.message), None
        )
        assert port_error is not None, f"No error mentioning 'port' in {errors}"

    def test_deprecated_key_graphrag_use_llm_extraction(self) -> None:
        """Test 8: graphrag.use_llm_extraction (legacy) returns deprecation error."""
        config = {
            "embedding": {"provider": "openai"},
            "graphrag": {
                "enabled": True,
                "use_llm_extraction": True,  # deprecated, renamed to doc_extractor
            },
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        deprecated_error = next(
            (
                e
                for e in errors
                if "use_llm_extraction" in e.field
                or "use_llm_extraction" in e.message
                or "doc_extractor" in e.suggestion
            ),
            None,
        )
        assert (
            deprecated_error is not None
        ), f"No deprecation error for graphrag.use_llm_extraction in {errors}"
        assert "doc_extractor" in deprecated_error.suggestion

    def test_valid_graphrag_doc_extractor_langextract(self) -> None:
        """Test 9: graphrag.doc_extractor = 'langextract' is valid — no errors."""
        config = {
            "embedding": {"provider": "openai"},
            "graphrag": {
                "enabled": True,
                "store_type": "simple",
                "use_code_metadata": True,
                "doc_extractor": "langextract",
            },
        }
        errors = validate_config_dict(config)
        assert errors == [], f"Unexpected errors: {errors}"


class TestValidateConfigFile:
    """Tests for file-based validation with line-number tracking."""

    def test_file_line_numbers_are_populated(self, tmp_path: Path) -> None:
        """Test 7: errors from file-based validation include line_number > 0."""
        yaml_content = """\
embedding:
  provider: badprovider
  model: text-embedding-3-large
summarization:
  provider: anthropic
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        errors = validate_config_file(config_file)
        assert len(errors) >= 1
        field_error = next((e for e in errors if e.field == "embedding.provider"), None)
        assert field_error is not None
        assert field_error.line_number is not None
        assert field_error.line_number > 0

    def test_valid_file_returns_no_errors(self, tmp_path: Path) -> None:
        """Valid YAML file returns empty list."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(VALID_MINIMAL_YAML)
        errors = validate_config_file(config_file)
        assert errors == []

    def test_returns_configvalidationerror_instances(self, tmp_path: Path) -> None:
        """validate_config_file returns ConfigValidationError instances."""
        yaml_content = "embedding:\n  provider: wrong\n"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        errors = validate_config_file(config_file)
        for err in errors:
            assert isinstance(err, ConfigValidationError)
            assert hasattr(err, "field")
            assert hasattr(err, "message")
            assert hasattr(err, "line_number")
            assert hasattr(err, "suggestion")


class TestFormatValidationErrors:
    """Tests for format_validation_errors output."""

    def test_format_shows_field_and_suggestion(self) -> None:
        """Formatted output includes field name and suggestion."""
        errors = [
            ConfigValidationError(
                field="embedding.provider",
                message="Invalid embedding provider",
                line_number=3,
                suggestion="Use one of: openai, ollama, cohere, gemini",
            )
        ]
        output = format_validation_errors(errors)
        assert "embedding.provider" in output
        assert "openai" in output
        assert "3" in output  # line number

    def test_format_shows_line_none_gracefully(self) -> None:
        """Formatted output handles None line_number gracefully."""
        errors = [
            ConfigValidationError(
                field="foobar",
                message="Unknown key",
                line_number=None,
                suggestion="Remove this key",
            )
        ]
        output = format_validation_errors(errors)
        assert "foobar" in output
        # Should not crash, regardless of line_number being None


# ---------------------------------------------------------------------------
# Tests for 'agent-brain config validate' CLI command
# ---------------------------------------------------------------------------


class TestValidateCliCommand:
    """Tests for the CLI validate subcommand."""

    def test_validate_valid_config_exits_0(self, tmp_path: Path) -> None:
        """Valid config file: exit 0 with 'Config is valid' message."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(VALID_MINIMAL_YAML)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "validate", "--file", str(config_file)])
        assert (
            result.exit_code == 0
        ), f"Expected exit 0, got {result.exit_code}. Output: {result.output}"
        assert "Config is valid" in result.output

    def test_validate_invalid_config_exits_1(self, tmp_path: Path) -> None:
        """Invalid config file: exit non-zero with error field name in output."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "embedding:\n  provider: badprovider\n"
            "summarization:\n  provider: anthropic\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "validate", "--file", str(config_file)])
        assert (
            result.exit_code != 0
        ), f"Expected non-zero exit, got 0. Output: {result.output}"
        assert "embedding.provider" in result.output or "badprovider" in result.output

    def test_validate_json_valid(self, tmp_path: Path) -> None:
        """Valid config + --json: outputs valid=true JSON."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(VALID_MINIMAL_YAML)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["config", "validate", "--file", str(config_file), "--json"]
        )
        assert (
            result.exit_code == 0
        ), f"Exit code: {result.exit_code}, Output: {result.output}"
        data = json.loads(result.output)
        assert data["valid"] is True
        assert data["errors"] == []

    def test_validate_json_invalid(self, tmp_path: Path) -> None:
        """Invalid config + --json: outputs valid=false JSON with errors."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("embedding:\n  provider: badprovider\n")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["config", "validate", "--file", str(config_file), "--json"]
        )
        assert (
            result.exit_code != 0
        ), f"Expected non-zero exit, got 0. Output: {result.output}"
        data = json.loads(result.output)
        assert data["valid"] is False
        assert len(data["errors"]) >= 1

    def test_validate_no_config_exits_0(self) -> None:
        """No config file found: exit 0 with 'No config file found' message."""
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file", return_value=None
        ):
            result = runner.invoke(cli, ["config", "validate"])
        assert (
            result.exit_code == 0
        ), f"Exit code: {result.exit_code}, Output: {result.output}"
        assert "No config file found" in result.output


# ---------------------------------------------------------------------------
# Tests for nested storage.postgres.* key validation
# ---------------------------------------------------------------------------


class TestNestedPostgresValidation:
    """Tests for nested storage.postgres.* key validation."""

    def test_valid_postgres_config_no_errors(self) -> None:
        """All known postgres keys with backend=postgres produces no errors."""
        config = {
            "storage": {
                "backend": "postgres",
                "postgres": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "agent_brain",
                    "user": "agent_brain",
                    "password": "secret",
                    "pool_size": 10,
                    "pool_max_overflow": 10,
                    "pool_timeout": 30,
                    "language": "english",
                    "hnsw_m": 16,
                    "hnsw_ef_construction": 64,
                    "debug": False,
                },
            }
        }
        errors = validate_config_dict(config)
        assert errors == [], f"Unexpected errors for valid postgres config: {errors}"

    def test_unknown_postgres_key_returns_error(self) -> None:
        """Config with storage.postgres.bad_key returns error with field path."""
        config = {
            "storage": {
                "backend": "postgres",
                "postgres": {"bad_key": True},
            }
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        pg_error = next(
            (e for e in errors if e.field == "storage.postgres.bad_key"), None
        )
        assert (
            pg_error is not None
        ), f"Expected error for storage.postgres.bad_key, got: {errors}"
        # Suggestion must mention known fields
        assert "Known fields:" in pg_error.suggestion

    def test_pool_timeout_accepted(self) -> None:
        """Config with storage.postgres.pool_timeout: 45 produces no errors."""
        config = {
            "storage": {
                "backend": "postgres",
                "postgres": {"pool_timeout": 45},
            }
        }
        errors = validate_config_dict(config)
        pg_timeout_error = next((e for e in errors if "pool_timeout" in e.field), None)
        assert (
            pg_timeout_error is None
        ), f"Unexpected error for pool_timeout: {pg_timeout_error}"

    def test_pool_timeout_wrong_type_returns_error(self) -> None:
        """Config with storage.postgres.pool_timeout: 'thirty' returns type error."""
        config = {
            "storage": {
                "backend": "postgres",
                "postgres": {"pool_timeout": "thirty"},
            }
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        type_error = next((e for e in errors if "pool_timeout" in e.field), None)
        assert (
            type_error is not None
        ), f"Expected type error for pool_timeout, got: {errors}"
        assert "must be an integer" in type_error.message

    def test_all_known_postgres_keys_accepted(self) -> None:
        """All 12 known postgres keys set to valid values produce no postgres errors."""
        all_known_keys = {
            "host": "localhost",
            "port": 5432,
            "database": "agent_brain",
            "user": "agent_brain",
            "password": "secret",
            "pool_size": 10,
            "pool_max_overflow": 5,
            "pool_timeout": 30,
            "language": "english",
            "hnsw_m": 16,
            "hnsw_ef_construction": 64,
            "debug": False,
        }
        assert (
            set(all_known_keys.keys()) == POSTGRES_KNOWN_FIELDS
        ), "Test must cover exactly the POSTGRES_KNOWN_FIELDS set"
        config = {
            "storage": {
                "backend": "postgres",
                "postgres": all_known_keys,
            }
        }
        errors = validate_config_dict(config)
        postgres_errors = [e for e in errors if "storage.postgres." in e.field]
        assert (
            postgres_errors == []
        ), f"Unexpected errors for known postgres keys: {postgres_errors}"

    def test_typo_in_postgres_key_is_caught(self) -> None:
        """Config with storage.postgres.pool_timeot (typo) returns error."""
        config = {
            "storage": {
                "backend": "postgres",
                "postgres": {"pool_timeot": 99},
            }
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 1
        typo_error = next((e for e in errors if "pool_timeot" in e.field), None)
        assert (
            typo_error is not None
        ), f"Expected error for pool_timeot typo, got: {errors}"
        assert typo_error.field == "storage.postgres.pool_timeot"
