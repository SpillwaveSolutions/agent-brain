"""Pluggable secrets resolution for production deployments.

Supports plain environment values (default, unchanged for local dev) and
``secret://`` references resolved via GCP Secret Manager when
``AGENT_BRAIN_SECRETS_BACKEND=gcp-secret-manager``.

Reference syntax::

    secret://env/OPENAI_API_KEY
    secret://gcp/projects/my-proj/secrets/openai-key/versions/latest
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import ClassVar
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SECRET_SCHEME = "secret"
_GCP_REF_RE = re.compile(
    r"^projects/(?P<project>[^/]+)/secrets/(?P<secret>[^/]+)/versions/(?P<version>.+)$"
)


class SecretsBackend(str, Enum):
    """Supported secrets backends."""

    ENV = "env"
    GCP_SECRET_MANAGER = "gcp-secret-manager"


class SecretsError(RuntimeError):
    """Raised when a secret reference cannot be resolved."""


@dataclass(frozen=True)
class GcpSecretRef:
    """Parsed GCP Secret Manager reference."""

    project: str
    secret_id: str
    version: str

    @property
    def resource_name(self) -> str:
        return (
            f"projects/{self.project}/secrets/{self.secret_id}/versions/{self.version}"
        )


def is_secret_reference(value: str | None) -> bool:
    """Return True when *value* is a ``secret://`` reference."""
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == SECRET_SCHEME


def parse_gcp_secret_ref(path: str) -> GcpSecretRef:
    """Parse the path portion of a ``secret://gcp/...`` reference."""
    match = _GCP_REF_RE.match(path.lstrip("/"))
    if not match:
        raise SecretsError(
            "Invalid GCP secret reference. Expected "
            "secret://gcp/projects/PROJECT/secrets/NAME/versions/VERSION"
        )
    return GcpSecretRef(
        project=match.group("project"),
        secret_id=match.group("secret"),
        version=match.group("version"),
    )


class SecretsResolver(ABC):
    """Resolve configuration values that may be plain text or secret refs."""

    @abstractmethod
    def resolve(self, value: str | None) -> str | None:
        """Resolve *value*, returning ``None`` for empty input."""


class EnvSecretsResolver(SecretsResolver):
    """Default resolver: plain values pass through; ``secret://env/VAR`` indirects."""

    def resolve(self, value: str | None) -> str | None:
        if not value:
            return None
        if not is_secret_reference(value):
            return value
        parsed = urlparse(value)
        if parsed.netloc != "env":
            raise SecretsError(
                f"Env secrets backend cannot resolve {value!r}. "
                "Set AGENT_BRAIN_SECRETS_BACKEND=gcp-secret-manager for GCP refs."
            )
        env_name = parsed.path.lstrip("/")
        if not env_name:
            raise SecretsError("secret://env/ reference requires a variable name")
        return os.environ.get(env_name)


class GcpSecretManagerResolver(SecretsResolver):
    """Resolve ``secret://gcp/...`` via the GCP Secret Manager API."""

    _cache: ClassVar[dict[str, str]] = {}

    def resolve(self, value: str | None) -> str | None:
        if not value:
            return None
        if not is_secret_reference(value):
            return value
        parsed = urlparse(value)
        if parsed.netloc == "env":
            env_name = parsed.path.lstrip("/")
            raw = os.environ.get(env_name)
            return self.resolve(raw) if raw else None
        if parsed.netloc != "gcp":
            raise SecretsError(
                f"Unsupported secret reference host {parsed.netloc!r} in {value!r}"
            )
        ref = parse_gcp_secret_ref(parsed.path)
        if ref.resource_name in self._cache:
            return self._cache[ref.resource_name]
        payload = self._fetch_secret(ref)
        self._cache[ref.resource_name] = payload
        return payload

    def _fetch_secret(self, ref: GcpSecretRef) -> str:
        try:
            from google.cloud import secretmanager
        except ImportError as exc:
            raise SecretsError(
                "GCP Secret Manager backend requires google-cloud-secret-manager. "
                "Install with: pip install 'agent-brain-rag[gcp]'"
            ) from exc

        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(name=ref.resource_name)
        decoded: str = response.payload.data.decode("utf-8")
        logger.debug("Resolved GCP secret %s", ref.secret_id)
        return decoded


def create_secrets_resolver(
    backend: str | None = None,
) -> SecretsResolver:
    """Build a resolver for ``backend``.

    Defaults to ``AGENT_BRAIN_SECRETS_BACKEND`` when *backend* is omitted.
    """
    selected = (
        backend or os.environ.get("AGENT_BRAIN_SECRETS_BACKEND") or "env"
    ).lower()
    if selected in {SecretsBackend.ENV.value, "env"}:
        return EnvSecretsResolver()
    if selected in {SecretsBackend.GCP_SECRET_MANAGER.value, "gcp"}:
        return GcpSecretManagerResolver()
    supported = f"{SecretsBackend.ENV.value}, {SecretsBackend.GCP_SECRET_MANAGER.value}"
    raise SecretsError(
        f"Unknown AGENT_BRAIN_SECRETS_BACKEND {selected!r}. " f"Supported: {supported}"
    )


@lru_cache
def get_secrets_resolver() -> SecretsResolver:
    """Return the process-wide cached secrets resolver."""
    return create_secrets_resolver()


def resolve_secret(value: str | None) -> str | None:
    """Resolve *value* using the configured secrets backend."""
    return get_secrets_resolver().resolve(value)


def resolve_env(name: str) -> str | None:
    """Read an environment variable and resolve any ``secret://`` reference."""
    return resolve_secret(os.environ.get(name))


def clear_secrets_resolver_cache() -> None:
    """Clear cached resolver and GCP payload cache (for tests)."""
    get_secrets_resolver.cache_clear()
    GcpSecretManagerResolver._cache.clear()
