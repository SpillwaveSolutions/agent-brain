"""Adversarial tests for the injector script allowlist (issue #181).

These tests exercise the fail-closed default, exact-hash matching, project ↔
global precedence, and the path-resolution rules that have to hold for
the allowlist to be a real trust boundary instead of a speed bump.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from agent_brain_server.services import injector_allowlist
from agent_brain_server.services.injector_allowlist import (
    assert_allowlisted,
    is_allowlisted,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Yield a tmp_path containing a `.agent-brain/config.yaml` (initially empty).

    Also clears all global config locations and the env-override so the test
    runs against ONLY the file we control, with no leakage from the operator's
    real ~/.agent-brain/config.yaml.
    """
    # Point the env override at this config file so discovery is fully deterministic
    # — no chdir, no walk-up surprises.
    cfg_dir = tmp_path / ".agent-brain"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setenv("AGENT_BRAIN_INJECTOR_ALLOWLIST_CONFIG", str(cfg_file))

    # Neutralize global discovery so legacy/XDG configs on the developer's
    # machine cannot accidentally allowlist an attacker script during tests.
    monkeypatch.setattr(
        injector_allowlist, "_global_config_paths", lambda: [], raising=True
    )
    return cfg_file


def _script(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_yaml(cfg: Path, body: str) -> None:
    cfg.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Fail-closed default
# ---------------------------------------------------------------------------


def test_missing_config_rejects_all_scripts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No config anywhere -> every script rejected."""
    monkeypatch.delenv("AGENT_BRAIN_INJECTOR_ALLOWLIST_CONFIG", raising=False)
    monkeypatch.setattr(
        injector_allowlist, "_project_config_paths", lambda: [], raising=True
    )
    monkeypatch.setattr(
        injector_allowlist, "_global_config_paths", lambda: [], raising=True
    )
    script = _script(tmp_path, "any.py", "def process_chunk(c): return c\n")
    with pytest.raises(PermissionError, match="not in the allowlist"):
        assert_allowlisted(script)
    assert is_allowlisted(script) is False


def test_empty_injector_scripts_list_rejects(
    isolated_config: Path, tmp_path: Path
) -> None:
    """Config exists but injector_scripts is empty -> reject."""
    _write_yaml(isolated_config, "injector_scripts: []\n")
    script = _script(tmp_path, "any.py", "def process_chunk(c): return c\n")
    with pytest.raises(PermissionError, match="not in the allowlist"):
        assert_allowlisted(script)


def test_missing_injector_scripts_key_rejects(
    isolated_config: Path, tmp_path: Path
) -> None:
    """Config has other keys but no injector_scripts -> reject."""
    _write_yaml(isolated_config, "providers: {embeddings: {provider: openai}}\n")
    script = _script(tmp_path, "any.py", "def process_chunk(c): return c\n")
    with pytest.raises(PermissionError, match="not in the allowlist"):
        assert_allowlisted(script)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_allowlisted_path_with_matching_hash_passes(
    isolated_config: Path, tmp_path: Path
) -> None:
    """Path + correct hash -> assert_allowlisted returns without raising."""
    script = _script(tmp_path, "good.py", "def process_chunk(c): return c\n")
    _write_yaml(
        isolated_config,
        f"injector_scripts:\n  - path: {script}\n    sha256: {_sha256(script)}\n",
    )
    assert_allowlisted(script)  # must not raise
    assert is_allowlisted(script) is True


# ---------------------------------------------------------------------------
# Adversarial: hash tampering
# ---------------------------------------------------------------------------


def test_tampered_script_is_rejected(isolated_config: Path, tmp_path: Path) -> None:
    """Script swapped after allowlisting -> hash mismatch rejection."""
    script = _script(tmp_path, "swap.py", "def process_chunk(c): return c\n")
    _write_yaml(
        isolated_config,
        f"injector_scripts:\n  - path: {script}\n    sha256: {_sha256(script)}\n",
    )
    # Attacker swaps the file
    script.write_text(
        "import os\n"
        "def process_chunk(c):\n"
        "    c['leak'] = os.environ.get('OPENAI_API_KEY', '')\n"
        "    return c\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="hash does not match"):
        assert_allowlisted(script)


def test_wrong_hash_in_allowlist_is_rejected(
    isolated_config: Path, tmp_path: Path
) -> None:
    """Operator's wrong sha256 -> rejection (catches typos and tampered config)."""
    script = _script(tmp_path, "ok.py", "def process_chunk(c): return c\n")
    # Use an all-'a' hash so YAML keeps it as a string. (An all-zero hash would
    # parse as an int and trigger the "needs strings" entry-skip path instead.)
    wrong_hash = "a" * 64
    _write_yaml(
        isolated_config,
        f"injector_scripts:\n  - path: {script}\n    sha256: {wrong_hash}\n",
    )
    with pytest.raises(PermissionError, match="hash does not match"):
        assert_allowlisted(script)


# ---------------------------------------------------------------------------
# Adversarial: malformed entries
# ---------------------------------------------------------------------------


def test_malformed_sha256_entry_is_skipped(
    isolated_config: Path, tmp_path: Path
) -> None:
    """An entry with an invalid sha256 doesn't allowlist anything."""
    script = _script(tmp_path, "shaped.py", "def process_chunk(c): return c\n")
    _write_yaml(
        isolated_config,
        f"injector_scripts:\n  - path: {script}\n    sha256: not-a-hash\n",
    )
    with pytest.raises(PermissionError, match="not in the allowlist"):
        assert_allowlisted(script)


def test_one_bad_entry_does_not_disable_others(
    isolated_config: Path, tmp_path: Path
) -> None:
    """A garbage entry next to a valid one doesn't open or close the gate wrongly."""
    good = _script(tmp_path, "good.py", "def process_chunk(c): return c\n")
    bad_path = tmp_path / "bad.py"  # never created
    _write_yaml(
        isolated_config,
        "injector_scripts:\n"
        f"  - path: {bad_path}\n    sha256: zz\n"  # invalid
        f"  - path: {good}\n    sha256: {_sha256(good)}\n",
    )
    assert_allowlisted(good)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_relative_path_in_config_is_resolved_relative_to_config_file(
    isolated_config: Path, tmp_path: Path
) -> None:
    """A relative `path:` like ./scripts/x.py resolves against the config dir."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = _script(scripts_dir, "x.py", "def process_chunk(c): return c\n")
    # cfg lives at <tmp_path>/.agent-brain/config.yaml; relative path is from there.
    rel = Path("..") / "scripts" / "x.py"
    _write_yaml(
        isolated_config,
        f"injector_scripts:\n  - path: {rel}\n    sha256: {_sha256(script)}\n",
    )
    assert_allowlisted(script)


def test_request_via_different_unresolved_path_still_matches(
    isolated_config: Path, tmp_path: Path
) -> None:
    """Allowlist keys by resolved path; equivalent unresolved paths still match."""
    script = _script(tmp_path, "x.py", "def process_chunk(c): return c\n")
    _write_yaml(
        isolated_config,
        f"injector_scripts:\n  - path: {script}\n    sha256: {_sha256(script)}\n",
    )
    # Build an equivalent path with /./ in it
    equivalent = Path(str(tmp_path) + "/./x.py")
    assert_allowlisted(equivalent)


# ---------------------------------------------------------------------------
# Project precedence over global
# ---------------------------------------------------------------------------


def test_project_entry_wins_over_global_for_same_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When project and global list the same path, project's hash wins."""
    project_cfg = tmp_path / "proj" / ".agent-brain" / "config.yaml"
    global_cfg = tmp_path / "global" / "config.yaml"
    project_cfg.parent.mkdir(parents=True)
    global_cfg.parent.mkdir(parents=True)

    script = _script(tmp_path, "shared.py", "def process_chunk(c): return c\n")
    real_hash = _sha256(script)

    # Project: correct hash. Global: wrong (but well-formed) hash.
    # Using all-'b' so YAML keeps it as a string (an all-digit hash parses as int).
    _write_yaml(
        project_cfg,
        f"injector_scripts:\n  - path: {script}\n    sha256: {real_hash}\n",
    )
    _write_yaml(
        global_cfg,
        f"injector_scripts:\n  - path: {script}\n    sha256: {'b' * 64}\n",
    )

    monkeypatch.setattr(
        injector_allowlist, "_project_config_paths", lambda: [project_cfg]
    )
    monkeypatch.setattr(
        injector_allowlist, "_global_config_paths", lambda: [global_cfg]
    )
    monkeypatch.delenv("AGENT_BRAIN_INJECTOR_ALLOWLIST_CONFIG", raising=False)

    # Project's correct hash wins → must pass
    assert_allowlisted(script)


def test_global_entry_is_used_when_project_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Global allowlist is consulted when project doesn't cover the script."""
    global_cfg = tmp_path / "global" / "config.yaml"
    global_cfg.parent.mkdir(parents=True)
    script = _script(tmp_path, "g.py", "def process_chunk(c): return c\n")
    _write_yaml(
        global_cfg,
        f"injector_scripts:\n  - path: {script}\n    sha256: {_sha256(script)}\n",
    )

    monkeypatch.setattr(injector_allowlist, "_project_config_paths", lambda: [])
    monkeypatch.setattr(
        injector_allowlist, "_global_config_paths", lambda: [global_cfg]
    )
    monkeypatch.delenv("AGENT_BRAIN_INJECTOR_ALLOWLIST_CONFIG", raising=False)

    assert_allowlisted(script)
