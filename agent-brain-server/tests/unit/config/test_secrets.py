"""Unit tests for secrets resolution (#219 P-A)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.config.secrets import (
    EnvSecretsResolver,
    GcpSecretManagerResolver,
    SecretsError,
    clear_secrets_resolver_cache,
    create_secrets_resolver,
    is_secret_reference,
    parse_gcp_secret_ref,
    resolve_secret,
)


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    clear_secrets_resolver_cache()


class TestSecretReferenceParsing:
    def test_is_secret_reference_true(self) -> None:
        assert is_secret_reference("secret://env/OPENAI_API_KEY")

    def test_is_secret_reference_false_for_plain(self) -> None:
        assert not is_secret_reference("sk-plain-key")

    def test_parse_gcp_secret_ref(self) -> None:
        ref = parse_gcp_secret_ref(
            "/projects/my-proj/secrets/openai-key/versions/latest"
        )
        assert ref.project == "my-proj"
        assert ref.secret_id == "openai-key"
        assert ref.version == "latest"
        assert ref.resource_name == (
            "projects/my-proj/secrets/openai-key/versions/latest"
        )


class TestEnvSecretsResolver:
    def test_plain_value_passes_through(self) -> None:
        resolver = EnvSecretsResolver()
        assert resolver.resolve("plain-secret") == "plain-secret"

    def test_env_indirection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "resolved-value")
        resolver = EnvSecretsResolver()
        assert resolver.resolve("secret://env/MY_KEY") == "resolved-value"

    def test_gcp_ref_rejected_on_env_backend(self) -> None:
        resolver = EnvSecretsResolver()
        with pytest.raises(SecretsError, match="gcp-secret-manager"):
            resolver.resolve("secret://gcp/projects/p/secrets/s/versions/latest")


class TestGcpSecretManagerResolver:
    def test_fetches_gcp_secret(self) -> None:
        resolver = GcpSecretManagerResolver()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.payload.data = b"super-secret"
        mock_client.access_secret_version.return_value = mock_response
        mock_module = MagicMock()
        mock_module.SecretManagerServiceClient.return_value = mock_client

        with patch.dict(
            sys.modules,
            {
                "google.cloud.secretmanager": mock_module,
            },
        ):
            value = resolver.resolve(
                "secret://gcp/projects/p/secrets/db-pass/versions/3"
            )

        assert value == "super-secret"
        mock_client.access_secret_version.assert_called_once_with(
            name="projects/p/secrets/db-pass/versions/3"
        )

    def test_missing_dependency_raises_clear_error(self) -> None:
        resolver = GcpSecretManagerResolver()
        import builtins

        real_import = builtins.__import__

        def _import(name: str, *args: object, **kwargs: object):
            if name == "google.cloud.secretmanager" or name.startswith("google.cloud"):
                raise ImportError("no gcp")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_import):
            with pytest.raises(SecretsError, match="google-cloud-secret-manager"):
                resolver._fetch_secret(
                    parse_gcp_secret_ref("/projects/p/secrets/s/versions/latest")
                )


class TestCreateSecretsResolver:
    def test_default_env_backend(self) -> None:
        resolver = create_secrets_resolver("env")
        assert isinstance(resolver, EnvSecretsResolver)

    def test_gcp_backend(self) -> None:
        resolver = create_secrets_resolver("gcp-secret-manager")
        assert isinstance(resolver, GcpSecretManagerResolver)

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(SecretsError, match="Unknown"):
            create_secrets_resolver("vault")


class TestResolveSecretIntegration:
    def test_resolve_secret_uses_env_backend_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AGENT_BRAIN_SECRETS_BACKEND", raising=False)
        monkeypatch.setenv("PLAIN_KEY", "from-env")
        assert resolve_secret("secret://env/PLAIN_KEY") == "from-env"
