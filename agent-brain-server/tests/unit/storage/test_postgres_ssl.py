"""Unit tests for PostgreSQL SSL connect_args (#219 P-A)."""

from __future__ import annotations

import ssl

import pytest

from agent_brain_server.storage.postgres.config import PostgresConfig
from agent_brain_server.storage.postgres.ssl import (
    build_connect_args,
    build_ssl_context,
)


class TestBuildSslContext:
    def test_disable_returns_false(self) -> None:
        config = PostgresConfig(ssl_mode="disable")
        assert build_ssl_context(config) is False

    def test_require_disables_verification(self) -> None:
        config = PostgresConfig(ssl_mode="require")
        ctx = build_ssl_context(config)
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.verify_mode == ssl.CERT_NONE
        assert ctx.check_hostname is False

    def test_verify_full_enforces_hostname(self) -> None:
        config = PostgresConfig(ssl_mode="verify-full")
        ctx = build_ssl_context(config)
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True


class TestBuildConnectArgs:
    def test_direct_includes_ssl(self) -> None:
        config = PostgresConfig(ssl_mode="require")
        args = build_connect_args(config)
        assert "ssl" in args
        assert args["ssl"] is not False

    def test_cloud_sql_proxy_sets_application_name(self) -> None:
        config = PostgresConfig(
            connection_strategy="cloud_sql_proxy", ssl_mode="disable"
        )
        args = build_connect_args(config)
        assert args["server_settings"]["application_name"] == "agent-brain"

    def test_cloud_sql_connector_not_implemented(self) -> None:
        config = PostgresConfig(connection_strategy="cloud_sql_connector")
        with pytest.raises(NotImplementedError, match="cloud_sql_connector"):
            build_connect_args(config)
