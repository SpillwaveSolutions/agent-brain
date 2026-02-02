"""Tests for server entry point installation and functionality."""

import pytest
from click.testing import CliRunner


class TestServerCLI:
    """Test server CLI entry point with Click."""

    def test_cli_function_importable(self):
        """Verify cli() function can be imported from agent_brain_server.api.main."""
        from agent_brain_server.api.main import cli

        assert callable(cli), "cli should be a callable function"

    def test_cli_is_click_command(self):
        """Verify cli is a Click command."""
        import click

        from agent_brain_server.api.main import cli

        assert isinstance(cli, click.core.Command), "cli should be a Click Command"

    def test_help_flag_returns_usage(self):
        """T045: Verify --help returns expected output."""
        from agent_brain_server.api.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert (
            result.exit_code == 0
        ), f"--help should exit with 0, got {result.exit_code}"
        assert "Usage:" in result.output, "--help should show usage"
        assert (
            "Agent Brain RAG Server" in result.output
        ), "--help should show description"

    def test_help_shows_options(self):
        """Verify --help lists available options."""
        from agent_brain_server.api.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert "--host" in result.output, "Should list --host option"
        assert "--port" in result.output, "Should list --port option"
        assert "--reload" in result.output, "Should list --reload option"
        assert "--version" in result.output, "Should list --version option"

    def test_version_flag_returns_version(self):
        """T046: Verify --version returns version string."""
        from agent_brain_server.api.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert (
            result.exit_code == 0
        ), f"--version should exit with 0, got {result.exit_code}"
        assert (
            "2.0.0" in result.output
        ), f"Should show version 2.0.0, got: {result.output}"


class TestServerEntryPoint:
    """Test server entry point is properly configured and functional."""

    def test_run_function_importable(self):
        """T019: Verify run() function can be imported."""
        from agent_brain_server.api.main import run

        assert callable(run), "run should be a callable function"

    def test_app_importable(self):
        """Verify FastAPI app can be imported."""
        from fastapi import FastAPI

        from agent_brain_server.api.main import app

        assert isinstance(app, FastAPI), "app should be a FastAPI instance"

    def test_version_importable(self):
        """Verify __version__ can be imported."""
        from agent_brain_server import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        assert __version__ == "2.0.0"


class TestServerApp:
    """Test FastAPI app is properly configured."""

    def test_app_has_title(self):
        """Verify app has correct title."""
        from agent_brain_server.api.main import app

        assert app.title == "Agent Brain RAG API"

    def test_app_has_version(self):
        """Verify app has version."""
        from agent_brain_server.api.main import app

        assert app.version == "2.0.0"

    def test_app_has_docs_url(self):
        """Verify docs URL is configured."""
        from agent_brain_server.api.main import app

        assert app.docs_url == "/docs"

    def test_app_has_openapi_url(self):
        """Verify OpenAPI URL is configured."""
        from agent_brain_server.api.main import app

        assert app.openapi_url == "/openapi.json"


class TestServerRouters:
    """Test that routers are registered."""

    def test_health_router_registered(self):
        """Verify health router is included."""
        from agent_brain_server.api.main import app

        routes = [route.path for route in app.routes]
        # Check for health-related routes
        health_routes = [r for r in routes if "/health" in r]
        assert len(health_routes) > 0, "Health router should be registered"

    def test_index_router_registered(self):
        """Verify index router is included."""
        from agent_brain_server.api.main import app

        routes = [route.path for route in app.routes]
        index_routes = [r for r in routes if "/index" in r]
        assert len(index_routes) > 0, "Index router should be registered"

    def test_query_router_registered(self):
        """Verify query router is included."""
        from agent_brain_server.api.main import app

        routes = [route.path for route in app.routes]
        query_routes = [r for r in routes if "/query" in r]
        assert len(query_routes) > 0, "Query router should be registered"


class TestServerSmokeTest:
    """Smoke test for server startup."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """T020: Verify server responds to root endpoint."""
        from httpx import ASGITransport, AsyncClient

        from agent_brain_server.api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "Agent Brain RAG API"

    @pytest.mark.asyncio
    async def test_docs_endpoint_accessible(self):
        """Verify /docs endpoint is accessible."""
        from httpx import ASGITransport, AsyncClient

        from agent_brain_server.api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/docs")

        # Docs page returns HTML
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
