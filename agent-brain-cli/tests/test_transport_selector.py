"""Phase 3 TDD: ``agent_brain_cli.client.transport.open_client``.

The selector is a 3-line dispatcher: reads transport choice off the
Click context, calls ``resolve_transport``, then constructs either
``DocServeClient(base_url=...)`` (HTTP) or
``DocServeClient.from_httpx(make_client(socket_path=...))`` (UDS).

Plan §4.4, §12.3 #5 and #6.

RED until ``agent_brain_cli/client/transport.py`` ships.
"""

from __future__ import annotations

import os
import socket
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import click
import pytest


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    keys = [k for k in os.environ if k.startswith("AGENT_BRAIN_")]
    saved = {k: os.environ.pop(k) for k in keys}
    try:
        yield
    finally:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update(saved)


@pytest.fixture
def short_state_dir() -> Generator[Path, None, None]:
    base = Path(tempfile.mkdtemp(prefix="absrv-sel-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)


def _make_ctx(**obj: Any) -> click.Context:
    """Build a Click context with the given ``ctx.obj`` payload."""
    cmd = click.Command("test")
    ctx = click.Context(cmd)
    ctx.obj = dict(obj)
    return ctx


class TestOpenClientHttp:
    """``open_client(ctx)`` → HTTP path returns ``DocServeClient``
    pointed at the resolved URL."""

    def test_http_transport_uses_base_url(self, clean_env: None) -> None:
        from agent_brain_cli.client.api_client import DocServeClient
        from agent_brain_cli.client.transport import open_client

        ctx = _make_ctx(
            transport_hint="http",
            base_url_override="http://127.0.0.1:9001",
        )
        client = open_client(ctx)
        try:
            assert isinstance(client, DocServeClient)
            assert client.base_url == "http://127.0.0.1:9001"
        finally:
            client.close()

    def test_http_transport_is_default_when_no_uds(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        from agent_brain_cli.client.api_client import DocServeClient
        from agent_brain_cli.client.transport import open_client

        ctx = _make_ctx(
            transport_hint="auto",
            socket_path_override=short_state_dir / "no-socket-here.sock",
            base_url_override="http://127.0.0.1:8000",
        )
        client = open_client(ctx)
        try:
            assert isinstance(client, DocServeClient)
            assert client.base_url == "http://127.0.0.1:8000"
        finally:
            client.close()


class TestOpenClientUds:
    """``open_client(ctx)`` → UDS path returns a wrapper with a
    UDS-backed inner httpx.Client."""

    def test_uds_transport_uses_socket(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        from agent_brain_cli.client.api_client import DocServeClient
        from agent_brain_cli.client.transport import open_client

        socket_path = short_state_dir / "agent-brain.sock"
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        os.chmod(short_state_dir, 0o700)
        try:
            ctx = _make_ctx(transport_hint="uds", socket_path_override=socket_path)
            client = open_client(ctx)
            try:
                assert isinstance(client, DocServeClient)
                # Inner httpx.Client base_url is the UDS sentinel.
                inner = client._client
                assert "agent-brain" in str(inner.base_url) or str(
                    inner.base_url
                ).startswith("http://")
            finally:
                client.close()
        finally:
            s.close()


class TestOpenClientEmptyContext:
    """``open_client(ctx)`` must tolerate ``ctx.obj is None`` —
    that's the state when no subcommand has populated it yet."""

    def test_none_ctx_obj_falls_back_to_defaults(self, clean_env: None) -> None:
        from agent_brain_cli.client.api_client import DocServeClient
        from agent_brain_cli.client.transport import open_client

        cmd = click.Command("test")
        ctx = click.Context(cmd)
        # ctx.obj defaults to None — open_client must handle this.
        os.environ["AGENT_BRAIN_URL"] = "http://127.0.0.1:8000"
        os.environ["AGENT_BRAIN_TRANSPORT"] = "http"
        client = open_client(ctx)
        try:
            assert isinstance(client, DocServeClient)
            assert client.base_url == "http://127.0.0.1:8000"
        finally:
            client.close()
