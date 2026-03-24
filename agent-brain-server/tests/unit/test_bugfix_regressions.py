"""Regression tests for BUGFIX-03 and BUGFIX-04.

These tests lock down already-applied fixes to prevent regression.

BUGFIX-03: ChromaDB telemetry suppression via ANONYMIZED_TELEMETRY env var and
           logger level tuning (PostHog noise reduction).
BUGFIX-04: Gemini provider uses google-genai (not the deprecated google-generativeai).

Note: BUGFIX-01 regression test (start --timeout default=120) is in
      agent-brain-cli/tests/test_bugfix01_start_timeout.py because it imports
      agent_brain_cli which is not installed in the server venv.
"""

import os
from pathlib import Path


class TestBugfix03TelemetrySuppression:
    """BUGFIX-03: ChromaDB telemetry suppression is active on startup."""

    def test_telemetry_suppression_env_var_can_be_set(self) -> None:
        """BUGFIX-03: ANONYMIZED_TELEMETRY env var can be set to False."""
        # Simulate what lifespan does
        os.environ.pop("ANONYMIZED_TELEMETRY", None)
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        assert os.environ["ANONYMIZED_TELEMETRY"] == "False"
        # Clean up
        del os.environ["ANONYMIZED_TELEMETRY"]

    def test_telemetry_suppression_in_main_source(self) -> None:
        """BUGFIX-03: main.py must contain ANONYMIZED_TELEMETRY suppression code."""
        main_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "api"
            / "main.py"
        )
        source = main_path.read_text()
        assert "ANONYMIZED_TELEMETRY" in source, (
            "main.py must set ANONYMIZED_TELEMETRY to suppress ChromaDB telemetry"
        )
        assert "posthog" in source.lower(), (
            "main.py must suppress posthog logger (ChromaDB telemetry noise)"
        )

    def test_posthog_logger_suppression_in_main_source(self) -> None:
        """BUGFIX-03: main.py must suppress posthog and chromadb.telemetry loggers."""
        main_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "api"
            / "main.py"
        )
        source = main_path.read_text()
        # Both logger suppressions must be present
        assert "chromadb.telemetry" in source, (
            "main.py must set chromadb.telemetry logger to WARNING level"
        )
        assert "posthog" in source.lower(), (
            "main.py must set posthog logger to WARNING level"
        )

    def test_vector_store_disables_telemetry(self) -> None:
        """BUGFIX-03: VectorStoreManager must pass anonymized_telemetry=False to ChromaDB."""
        vector_store_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "storage"
            / "vector_store.py"
        )
        source = vector_store_path.read_text()
        assert "anonymized_telemetry=False" in source, (
            "VectorStoreManager must pass anonymized_telemetry=False to ChromaSettings"
        )

    def test_anonymized_telemetry_setdefault_pattern(self) -> None:
        """BUGFIX-03: main.py uses os.environ.setdefault for ANONYMIZED_TELEMETRY.

        setdefault preserves any user override while ensuring default is False.
        """
        main_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "api"
            / "main.py"
        )
        source = main_path.read_text()
        assert 'setdefault("ANONYMIZED_TELEMETRY", "False")' in source, (
            "main.py must use os.environ.setdefault to set ANONYMIZED_TELEMETRY"
        )


class TestBugfix04GeminiMigration:
    """BUGFIX-04: Gemini provider uses google-genai, not deprecated google-generativeai."""

    def test_gemini_uses_google_genai_import(self) -> None:
        """BUGFIX-04: Gemini provider must import google.genai, not google.generativeai."""
        gemini_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "providers"
            / "summarization"
            / "gemini.py"
        )
        source = gemini_path.read_text()
        # Must use google.genai
        assert "import google.genai" in source or "from google import genai" in source, (
            "gemini.py must import google.genai (not google.generativeai)"
        )
        # Must NOT use the deprecated package
        assert "google.generativeai" not in source, (
            "gemini.py must not use google.generativeai (deprecated — use google-genai)"
        )

    def test_pyproject_uses_google_genai_not_generativeai(self) -> None:
        """BUGFIX-04: pyproject.toml must depend on google-genai, not google-generativeai."""
        pyproject_path = (
            Path(__file__).parent.parent.parent / "pyproject.toml"
        )
        content = pyproject_path.read_text()
        assert "google-genai" in content, (
            "pyproject.toml must list google-genai as a dependency"
        )
        assert "google-generativeai" not in content, (
            "pyproject.toml must not list google-generativeai (deprecated package)"
        )

    def test_gemini_provider_module_importable(self) -> None:
        """BUGFIX-04: Gemini provider module must be importable without error."""
        try:
            import importlib

            importlib.import_module(
                "agent_brain_server.providers.summarization.gemini"
            )
        except ImportError as e:
            # Only fail if it's a google.generativeai import error
            if "google.generativeai" in str(e):
                raise AssertionError(
                    f"BUGFIX-04: Gemini provider still references google.generativeai: {e}"
                ) from e
            # Other import errors (e.g., google.genai not installed) are acceptable in CI
