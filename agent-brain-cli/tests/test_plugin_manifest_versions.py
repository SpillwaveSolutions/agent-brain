"""Guard: every plugin/marketplace manifest reports the server version."""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _server_version() -> str:
    pyproject = REPO_ROOT / "agent-brain-server" / "pyproject.toml"
    for line in pyproject.read_text().splitlines():
        if line.startswith("version = "):
            return line.split('"')[1]
    raise AssertionError("server version not found")


class TestPluginManifestVersions:
    def test_all_manifests_match_server(self) -> None:
        expected = _server_version()
        plugin = REPO_ROOT / "agent-brain-plugin"
        paths = [
            plugin / ".claude-plugin" / "plugin.json",
            plugin / "plugin.json",
            plugin / ".codex-plugin" / "plugin.json",
            plugin / ".cursor-plugin" / "plugin.json",
        ]
        for path in paths:
            data = json.loads(path.read_text())
            assert data["version"] == expected, path

        market_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        market = json.loads(market_path.read_text())
        assert market["plugins"][0]["version"] == expected

        grok_path = plugin / ".grok-plugin" / "marketplace.json"
        grok = json.loads(grok_path.read_text())
        assert grok["version"] == expected
        assert grok["plugins"][0]["version"] == expected

    def test_check_script_exits_zero(self) -> None:
        script = REPO_ROOT / "scripts" / "check_plugin_manifest_versions.sh"
        result = subprocess.run(
            [str(script)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
