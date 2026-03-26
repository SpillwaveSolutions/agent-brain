"""Config schema validation engine for Agent Brain YAML config files.

Provides offline validation of config.yaml against the known Agent Brain schema,
reporting errors with field paths, line numbers, and fix suggestions.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Valid value sets
# ---------------------------------------------------------------------------

VALID_TOP_LEVEL_KEYS = {
    "embedding",
    "summarization",
    "reranker",
    "storage",
    "graphrag",
    "api",
    "server",
    "project",
}

VALID_EMBEDDING_PROVIDERS = {"openai", "ollama", "cohere", "gemini"}
VALID_SUMMARIZATION_PROVIDERS = {"anthropic", "openai", "ollama", "gemini", "grok"}
VALID_RERANKER_PROVIDERS = {"sentence-transformers", "ollama"}
VALID_STORAGE_BACKENDS = {"chroma", "postgres"}
VALID_GRAPHRAG_STORE_TYPES = {"simple", "kuzu"}
VALID_DOC_EXTRACTORS = {"langextract", "none"}

# Known sub-keys for each section — unknown keys trigger a warning
EMBEDDING_KNOWN_FIELDS = {
    "provider",
    "model",
    "api_key",
    "api_key_env",
    "base_url",
    "params",
}
SUMMARIZATION_KNOWN_FIELDS = {
    "provider",
    "model",
    "api_key",
    "api_key_env",
    "base_url",
    "params",
}
RERANKER_KNOWN_FIELDS = {
    "provider",
    "model",
    "base_url",
    "params",
}
STORAGE_KNOWN_FIELDS = {"backend", "postgres"}
POSTGRES_KNOWN_FIELDS = {
    "host",
    "port",
    "database",
    "user",
    "password",
    "pool_size",
    "pool_max_overflow",
    "pool_timeout",
    "language",
    "hnsw_m",
    "hnsw_ef_construction",
    "debug",
}
POSTGRES_TYPE_FIELDS: dict[str, tuple[type, str]] = {
    "port": (int, "storage.postgres.port must be an integer"),
    "pool_size": (int, "storage.postgres.pool_size must be an integer"),
    "pool_max_overflow": (int, "storage.postgres.pool_max_overflow must be an integer"),
    "pool_timeout": (int, "storage.postgres.pool_timeout must be an integer"),
    "hnsw_m": (int, "storage.postgres.hnsw_m must be an integer"),
    "hnsw_ef_construction": (
        int,
        "storage.postgres.hnsw_ef_construction must be an integer",
    ),
    "debug": (bool, "storage.postgres.debug must be a boolean (true/false)"),
}
GRAPHRAG_KNOWN_FIELDS = {
    "enabled",
    "store_type",
    "use_code_metadata",
    "doc_extractor",
}
API_KNOWN_FIELDS = {"host", "port"}
SERVER_KNOWN_FIELDS = {"url", "host", "port", "auto_port"}
PROJECT_KNOWN_FIELDS = {"state_dir", "project_root"}

# ---------------------------------------------------------------------------
# Deprecated key mapping: dot-path -> migration suggestion
# ---------------------------------------------------------------------------

DEPRECATED_KEYS: dict[str, str] = {
    "graphrag.use_llm_extraction": (
        "Renamed to 'graphrag.doc_extractor'. "
        "Use doc_extractor: langextract instead."
    ),
}

# ---------------------------------------------------------------------------
# Schema: section name -> (known_fields, enum_fields)
# ---------------------------------------------------------------------------

_SECTION_SCHEMA: dict[str, dict[str, Any]] = {
    "embedding": {
        "known_fields": EMBEDDING_KNOWN_FIELDS,
        "enum_fields": {
            "provider": (
                VALID_EMBEDDING_PROVIDERS,
                "Invalid embedding provider",
                f"Use one of: {', '.join(sorted(VALID_EMBEDDING_PROVIDERS))}",
            ),
        },
        "type_fields": {},
    },
    "summarization": {
        "known_fields": SUMMARIZATION_KNOWN_FIELDS,
        "enum_fields": {
            "provider": (
                VALID_SUMMARIZATION_PROVIDERS,
                "Invalid summarization provider",
                f"Use one of: {', '.join(sorted(VALID_SUMMARIZATION_PROVIDERS))}",
            ),
        },
        "type_fields": {},
    },
    "reranker": {
        "known_fields": RERANKER_KNOWN_FIELDS,
        "enum_fields": {
            "provider": (
                VALID_RERANKER_PROVIDERS,
                "Invalid reranker provider",
                f"Use one of: {', '.join(sorted(VALID_RERANKER_PROVIDERS))}",
            ),
        },
        "type_fields": {},
    },
    "storage": {
        "known_fields": STORAGE_KNOWN_FIELDS,
        "enum_fields": {
            "backend": (
                VALID_STORAGE_BACKENDS,
                "Invalid storage backend",
                f"Use one of: {', '.join(sorted(VALID_STORAGE_BACKENDS))}",
            ),
        },
        "type_fields": {},
    },
    "graphrag": {
        "known_fields": GRAPHRAG_KNOWN_FIELDS,
        "enum_fields": {
            "store_type": (
                VALID_GRAPHRAG_STORE_TYPES,
                "Invalid graphrag store_type",
                f"Use one of: {', '.join(sorted(VALID_GRAPHRAG_STORE_TYPES))}",
            ),
            "doc_extractor": (
                VALID_DOC_EXTRACTORS,
                "Invalid graphrag doc_extractor",
                f"Use one of: {', '.join(sorted(VALID_DOC_EXTRACTORS))}",
            ),
        },
        "type_fields": {
            "enabled": (bool, "graphrag.enabled must be a boolean (true/false)"),
            "use_code_metadata": (
                bool,
                "graphrag.use_code_metadata must be a boolean (true/false)",
            ),
        },
    },
    "api": {
        "known_fields": API_KNOWN_FIELDS,
        "enum_fields": {},
        "type_fields": {
            "port": (int, "api.port must be an integer"),
        },
    },
    "server": {
        "known_fields": SERVER_KNOWN_FIELDS,
        "enum_fields": {},
        "type_fields": {
            "port": (int, "server.port must be an integer"),
            "auto_port": (bool, "server.auto_port must be a boolean (true/false)"),
        },
    },
    "project": {
        "known_fields": PROJECT_KNOWN_FIELDS,
        "enum_fields": {},
        "type_fields": {},
    },
}


# ---------------------------------------------------------------------------
# ConfigValidationError dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConfigValidationError:
    """A single validation error found in a config.yaml file.

    Attributes:
        field: Dot-path to the offending field, e.g. "embedding.provider".
        message: Human-readable description of the problem.
        line_number: Approximate 1-indexed line in the YAML file, or None if
            the error was produced from a dict (no source text available).
        suggestion: Actionable fix text shown to the user.
    """

    field: str
    message: str
    line_number: int | None
    suggestion: str = dc_field(default="")


# ---------------------------------------------------------------------------
# Line-number helper
# ---------------------------------------------------------------------------


def _find_line_number(yaml_text: str, key_path: str) -> int | None:
    """Scan YAML text to find the approximate line of a dot-path key.

    Strategy: split key_path by ".", search for each segment starting from
    the line after the parent was found.  Returns a 1-indexed line number.

    Args:
        yaml_text: Raw YAML file content.
        key_path: Dot-separated key path, e.g. "embedding.provider".

    Returns:
        1-indexed line number, or None if not found.
    """
    segments = key_path.split(".")
    lines = yaml_text.splitlines()
    search_from = 0

    for segment in segments:
        found_at: int | None = None
        for i in range(search_from, len(lines)):
            stripped = lines[i].lstrip()
            # Match "segment:" or "segment :" at the start of a stripped line
            if stripped.startswith(f"{segment}:") or stripped == segment:
                found_at = i
                break
        if found_at is None:
            return None
        search_from = found_at + 1

    # Return 1-indexed line of the deepest segment
    if search_from > 0:
        return search_from  # search_from = found_at + 1, so this is 1-indexed
    return None


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def validate_config_dict(
    config: dict[str, Any],
) -> list[ConfigValidationError]:
    """Validate a config dict against the Agent Brain schema.

    Does NOT enrich errors with line numbers — that is done by
    :func:`validate_config_file`.

    Args:
        config: Parsed YAML config dictionary.

    Returns:
        List of :class:`ConfigValidationError` objects (empty if valid).
    """
    errors: list[ConfigValidationError] = []

    # 1. Check for unknown top-level keys
    for key in config:
        if key not in VALID_TOP_LEVEL_KEYS:
            errors.append(
                ConfigValidationError(
                    field=key,
                    message=f"Unknown top-level key '{key}'",
                    line_number=None,
                    suggestion=(
                        f"Remove or rename '{key}'. "
                        f"Valid keys: {', '.join(sorted(VALID_TOP_LEVEL_KEYS))}"
                    ),
                )
            )

    # 2. Per-section validation
    for section_name, schema in _SECTION_SCHEMA.items():
        section_data = config.get(section_name)
        if section_data is None:
            continue  # Section not present — that's fine, all sections optional
        if not isinstance(section_data, dict):
            actual_type = type(section_data).__name__
            errors.append(
                ConfigValidationError(
                    field=section_name,
                    message=(
                        f"'{section_name}' must be a mapping (dict),"
                        f" got {actual_type}"
                    ),
                    line_number=None,
                    suggestion=(
                        f"Ensure '{section_name}:' is followed by"
                        " indented key-value pairs."
                    ),
                )
            )
            continue

        known_fields: set[str] = schema["known_fields"]
        enum_fields: dict[str, tuple[set[str], str, str]] = schema["enum_fields"]
        type_fields: dict[str, tuple[type, str]] = schema["type_fields"]

        # 2a. Unknown sub-keys
        for sub_key in section_data:
            if sub_key not in known_fields:
                errors.append(
                    ConfigValidationError(
                        field=f"{section_name}.{sub_key}",
                        message=f"Unknown key '{sub_key}' in section '{section_name}'",
                        line_number=None,
                        suggestion=(
                            f"Remove '{sub_key}' or check for a typo. "
                            f"Known fields: {', '.join(sorted(known_fields))}"
                        ),
                    )
                )

        # 2b. Enum field validation
        for enum_key, (valid_values, msg, suggestion) in enum_fields.items():
            value = section_data.get(enum_key)
            if value is not None and str(value) not in valid_values:
                errors.append(
                    ConfigValidationError(
                        field=f"{section_name}.{enum_key}",
                        message=f"{msg}: '{value}'",
                        line_number=None,
                        suggestion=suggestion,
                    )
                )

        # 2c. Type validation
        for type_key, (expected_type, type_msg) in type_fields.items():
            value = section_data.get(type_key)
            if value is not None and not isinstance(value, expected_type):
                errors.append(
                    ConfigValidationError(
                        field=f"{section_name}.{type_key}",
                        message=type_msg,
                        line_number=None,
                        suggestion=(
                            f"Change '{type_key}' to a"
                            f" {expected_type.__name__} value."
                        ),
                    )
                )

    # 2d. Nested storage.postgres.* key validation
    storage_section = config.get("storage")
    if isinstance(storage_section, dict):
        postgres_data = storage_section.get("postgres")
        if isinstance(postgres_data, dict):
            for pg_key in postgres_data:
                if pg_key not in POSTGRES_KNOWN_FIELDS:
                    errors.append(
                        ConfigValidationError(
                            field=f"storage.postgres.{pg_key}",
                            message=f"Unknown key '{pg_key}' in storage.postgres",
                            line_number=None,
                            suggestion=(
                                f"Remove '{pg_key}' or check for a typo. "
                                "Known fields: "
                                f"{', '.join(sorted(POSTGRES_KNOWN_FIELDS))}"
                            ),
                        )
                    )
            # Type validation for postgres sub-keys
            for type_key, (expected_type, type_msg) in POSTGRES_TYPE_FIELDS.items():
                value = postgres_data.get(type_key)
                if value is not None and not isinstance(value, expected_type):
                    errors.append(
                        ConfigValidationError(
                            field=f"storage.postgres.{type_key}",
                            message=type_msg,
                            line_number=None,
                            suggestion=(
                                f"Change '{type_key}' to a"
                                f" {expected_type.__name__} value."
                            ),
                        )
                    )

    # 3. Check deprecated keys
    for deprecated_path, migration_hint in DEPRECATED_KEYS.items():
        parts = deprecated_path.split(".", 1)
        section_name = parts[0]
        sub_key = parts[1] if len(parts) > 1 else ""
        section_data = config.get(section_name)
        if isinstance(section_data, dict) and sub_key in section_data:
            errors.append(
                ConfigValidationError(
                    field=deprecated_path,
                    message=f"Deprecated key '{deprecated_path}'",
                    line_number=None,
                    suggestion=migration_hint,
                )
            )

    return errors


def validate_config_file(path: Path) -> list[ConfigValidationError]:
    """Validate a config.yaml file against the Agent Brain schema.

    Reads the file as raw text, parses with yaml.safe_load, calls
    :func:`validate_config_dict`, then enriches each error with a line number
    using :func:`_find_line_number`.

    Args:
        path: Path to the YAML config file.

    Returns:
        List of :class:`ConfigValidationError` objects (empty if valid).

    Raises:
        OSError: If the file cannot be read.
        yaml.YAMLError: If the YAML cannot be parsed.
    """
    yaml_text = path.read_text(encoding="utf-8")
    config: dict[str, Any] = yaml.safe_load(yaml_text) or {}
    errors = validate_config_dict(config)
    # Enrich with line numbers
    for error in errors:
        if error.line_number is None:
            error.line_number = _find_line_number(yaml_text, error.field)
    return errors


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_validation_errors(errors: list[ConfigValidationError]) -> str:
    """Format a list of validation errors into a human-readable string.

    Example output::

        Config validation errors:

          Line 3: embedding.provider = "badprovider"
            Error: Invalid embedding provider: 'badprovider'
            Fix: Use one of: cohere, gemini, ollama, openai

    Args:
        errors: List of :class:`ConfigValidationError` objects.

    Returns:
        Formatted multi-line string.
    """
    if not errors:
        return ""

    lines = ["Config validation errors:", ""]
    for error in errors:
        if error.line_number is not None:
            header = f"  Line {error.line_number}: {error.field}"
        else:
            header = f"  {error.field}"
        lines.append(header)
        lines.append(f"    Error: {error.message}")
        if error.suggestion:
            lines.append(f"    Fix: {error.suggestion}")
        lines.append("")
    return "\n".join(lines)
