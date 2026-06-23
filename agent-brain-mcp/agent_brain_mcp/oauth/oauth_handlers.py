"""OAuth 2.1 browser redirect handler and ephemeral loopback callback server.

Phase 69 Plan 02 -- browser/loopback UX for the OAuthClientProvider dance.

Provides
--------
build_redirect_handler
    Returns an ``async def _handler(url: str) -> None`` closure that opens
    the system browser to the authorization URL and prints the URL to *stderr*
    (or an injected stream) as a headless fallback.

LoopbackCallbackServer
    Binds an ``http.server.HTTPServer`` on ``127.0.0.1`` with port ``0`` so
    the OS assigns a free ephemeral port.  The ``redirect_uri`` property
    exposes ``http://127.0.0.1:<port>/callback`` *before* the dance begins,
    letting DCR register the correct ``redirect_uris``.  A single-shot
    ``wait_for_callback()`` coroutine serves one request, captures
    ``(code, state)`` from the query string, and shuts down.

build_callback_handler
    Wraps a ``LoopbackCallbackServer`` in the ``Callable[[], Awaitable[...]]``
    shape that ``OAuthClientProvider`` expects.

Decision C (69-CONTEXT.md)
--------------------------
- ``redirect_handler``: ``webbrowser.open(url)`` AND print URL to stderr.
- ``callback_handler``: ephemeral localhost HTTP on OS-assigned port; captures
  ``code + state``; returns a friendly "close this tab" page.
- Headless/CI: print URL and run the listener anyway; if no browser is
  available the dance blocks until timeout.  Never raise on a missing browser.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
"""

from __future__ import annotations

import asyncio
import http.server
import sys
import urllib.parse
import webbrowser
from collections.abc import Awaitable, Callable
from typing import IO

# ---------------------------------------------------------------------------
# Internal HTTP response bodies
# ---------------------------------------------------------------------------

_CLOSE_TAB_BODY = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Authentication complete</title></head>
<body>
<h1>Authentication complete</h1>
<p>You may close this tab.</p>
</body>
</html>
"""

_ERROR_BODY = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Authentication error</title></head>
<body>
<h1>Authentication error</h1>
<p>Missing authorization code. Please try again.</p>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Typed HTTPServer subclass
# ---------------------------------------------------------------------------


class _OAuthHTTPServer(http.server.HTTPServer):
    """HTTPServer subclass that carries the captured OAuth callback data.

    The request handler writes ``oauth_code`` and ``oauth_state`` onto this
    instance after parsing the redirect GET request.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialise with empty callback state."""
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.oauth_code: str | None = None
        self.oauth_state: str | None = None


# ---------------------------------------------------------------------------
# Request handler factory
# ---------------------------------------------------------------------------


def _make_handler_class(callback_path: str) -> type:
    """Create a ``BaseHTTPRequestHandler`` subclass for *callback_path*.

    Args:
        callback_path: The URL path that receives the OAuth redirect, e.g.
            ``"/callback"``.

    Returns:
        A ``BaseHTTPRequestHandler`` subclass that captures ``code`` and
        ``state`` query parameters and stashes them on the server instance as
        ``server.oauth_code`` / ``server.oauth_state``.
    """

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        """Single-shot callback handler for the OAuth loopback redirect."""

        def do_GET(self) -> None:  # noqa: N802 -- required by BaseHTTPRequestHandler
            """Handle GET /callback?code=...&state=..."""
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)

            code: str | None = None
            state: str | None = None

            if parsed.path == callback_path:
                code_list = qs.get("code")
                state_list = qs.get("state")
                code = code_list[0] if code_list else None
                state = state_list[0] if state_list else None

                if code is not None:
                    body = _CLOSE_TAB_BODY.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    body = _ERROR_BODY.encode()
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            else:
                body = b"Not found"
                self.send_response(404)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            # Stash on server so LoopbackCallbackServer can retrieve them.
            srv = self.server
            if isinstance(srv, _OAuthHTTPServer):
                srv.oauth_code = code
                srv.oauth_state = state

        def log_message(self, format: str, *args: object) -> None:
            """Silence default Apache-style access log output."""
            return

    return _CallbackHandler


# ---------------------------------------------------------------------------
# LoopbackCallbackServer
# ---------------------------------------------------------------------------


class LoopbackCallbackServer:
    """Ephemeral localhost HTTP server that captures an OAuth callback once.

    Binds to ``127.0.0.1:0`` so the OS assigns a free port.  The chosen port
    is available immediately via :attr:`port` and :attr:`redirect_uri`, which
    must be passed to ``OAuthClientMetadata.redirect_uris`` before the OAuth
    dance begins so that DCR registers the correct URI.

    Usage::

        with LoopbackCallbackServer() as srv:
            # Hand srv.redirect_uri to OAuthClientProvider before the dance.
            code, state = await srv.wait_for_callback()

    Args:
        host: Loopback address to bind on.  Defaults to ``"127.0.0.1"``.
        path: URL path that the OAuth provider redirects to.  Defaults to
            ``"/callback"``.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        path: str = "/callback",
    ) -> None:
        """Bind the HTTP server to an OS-assigned port.

        Args:
            host: Loopback address to bind.
            path: Callback URL path.
        """
        self._host = host
        self._path = path
        handler_cls = _make_handler_class(path)
        self._httpd = _OAuthHTTPServer((host, 0), handler_cls)
        self.port: int = self._httpd.server_address[1]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def redirect_uri(self) -> str:
        """Full redirect URI registered with the OAuth provider.

        Returns:
            ``"http://<host>:<port><path>"`` where *port* is the OS-assigned
            ephemeral port.
        """
        return f"http://{self._host}:{self.port}{self._path}"

    async def wait_for_callback(self) -> tuple[str, str | None]:
        """Serve exactly one request and return the captured ``(code, state)``.

        Runs ``HTTPServer.handle_request()`` in a thread pool executor so the
        event loop is not blocked.

        Returns:
            A ``(authorization_code, state)`` tuple.  *state* may be ``None``
            if the provider did not echo it back.

        Raises:
            RuntimeError: If the redirect did not include an authorization code.
        """
        await asyncio.to_thread(self._httpd.handle_request)
        code: str | None = self._httpd.oauth_code
        state: str | None = self._httpd.oauth_state
        if code is None:
            raise RuntimeError(
                "OAuth callback received no authorization code. "
                "The redirect request did not include a 'code' parameter."
            )
        return code, state

    def close(self) -> None:
        """Close the underlying server socket."""
        self._httpd.server_close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> LoopbackCallbackServer:
        """Enter context -- return self (server already bound in __init__)."""
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit context -- close the server socket."""
        self.close()


# ---------------------------------------------------------------------------
# build_redirect_handler
# ---------------------------------------------------------------------------


def build_redirect_handler(
    opener: Callable[[str], bool] | None = None,
    stream: IO[str] | None = None,
) -> Callable[[str], Awaitable[None]]:
    """Create an async redirect handler for ``OAuthClientProvider``.

    The returned coroutine:

    1. Prints ``"Open this URL to authorize:\\n<url>\\n"`` to *stream*
       (defaults to :data:`sys.stderr`) so headless environments have a
       fallback.
    2. Calls *opener* (defaults to :func:`webbrowser.open`) with the URL.
       Any exception raised by *opener* is swallowed so that running without a
       browser (e.g. in CI) does not crash the dance -- the printed URL is the
       only required output in that scenario.

    Args:
        opener: Callable that receives the authorization URL and opens a
            browser.  Must return a ``bool`` (the :func:`webbrowser.open`
            signature).  Defaults to :func:`webbrowser.open`.
        stream: Text stream for the URL fallback message.  Defaults to
            :data:`sys.stderr`.

    Returns:
        An ``async def _handler(url: str) -> None`` callable that satisfies
        the ``redirect_handler`` type expected by ``OAuthClientProvider``.
    """
    _opener: Callable[[str], bool] = opener if opener is not None else webbrowser.open

    async def _handler(url: str) -> None:
        """Open the authorization URL in a browser and print it to *stream*.

        Args:
            url: The full authorization URL to open.
        """
        _stream: IO[str] = stream if stream is not None else sys.stderr
        _stream.write(f"Open this URL to authorize:\n{url}\n")
        _stream.flush()
        try:
            _opener(url)
        except Exception:  # noqa: BLE001
            # Headless box or no browser -- the printed URL is the fallback.
            pass

    return _handler


# ---------------------------------------------------------------------------
# build_callback_handler
# ---------------------------------------------------------------------------


def build_callback_handler(
    server: LoopbackCallbackServer,
) -> Callable[[], Awaitable[tuple[str, str | None]]]:
    """Create an async callback handler wrapping *server*.

    The returned coroutine delegates to
    :meth:`LoopbackCallbackServer.wait_for_callback`.

    Args:
        server: A :class:`LoopbackCallbackServer` instance that is already
            bound and listening.

    Returns:
        An ``async def _handler() -> tuple[str, str | None]`` callable that
        satisfies the ``callback_handler`` type expected by
        ``OAuthClientProvider``.
    """

    async def _handler() -> tuple[str, str | None]:
        """Wait for the OAuth redirect and return ``(code, state)``.

        Returns:
            The ``(authorization_code, state)`` tuple from the loopback server.
        """
        return await server.wait_for_callback()

    return _handler
