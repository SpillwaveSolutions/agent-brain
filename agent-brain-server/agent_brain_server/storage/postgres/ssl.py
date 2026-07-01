"""SSL/TLS helpers for asyncpg connections via SQLAlchemy."""

from __future__ import annotations

import ssl
from typing import Any, Literal

from agent_brain_server.storage.postgres.config import PostgresConfig

SslMode = Literal["disable", "require", "verify-ca", "verify-full"]
ConnectionStrategy = Literal["direct", "cloud_sql_proxy", "cloud_sql_connector"]


def build_ssl_context(config: PostgresConfig) -> ssl.SSLContext | bool:
    """Build the ``ssl`` argument for asyncpg ``connect_args``.

    Returns ``False`` when SSL is disabled (asyncpg convention).
    """
    if config.ssl_mode == "disable":
        return False

    if config.ssl_root_cert:
        ctx = ssl.create_default_context(cafile=config.ssl_root_cert)
    else:
        ctx = ssl.create_default_context()

    if config.ssl_mode == "require":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    elif config.ssl_mode == "verify-ca":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
    elif config.ssl_mode == "verify-full":
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

    if config.ssl_cert and config.ssl_key:
        ctx.load_cert_chain(config.ssl_cert, config.ssl_key)

    return ctx


def build_connect_args(config: PostgresConfig) -> dict[str, Any]:
    """Build SQLAlchemy ``connect_args`` for the configured connection strategy."""
    if config.connection_strategy == "cloud_sql_connector":
        raise NotImplementedError(
            "connection_strategy=cloud_sql_connector requires the optional "
            "cloud-sql-python-connector package and cloud_sql_instance. "
            "Use cloud_sql_proxy (Auth Proxy sidecar on 127.0.0.1:5432) for "
            "the single-container GCP reference deployment."
        )

    connect_args: dict[str, Any] = {"ssl": build_ssl_context(config)}

    if config.connection_strategy == "cloud_sql_proxy":
        # The Auth Proxy terminates TLS; the app connects to loopback in-pod.
        connect_args["server_settings"] = {"application_name": "agent-brain"}

    return connect_args
