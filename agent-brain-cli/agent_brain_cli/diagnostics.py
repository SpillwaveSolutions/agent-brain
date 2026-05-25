"""Shared diagnostics helpers for the Agent Brain CLI.

The functions here power both the ``agent-brain doctor`` command and the
"tip: run doctor" hint that appears when a command can't reach the server.
Keeping the logic in one place means the hint and the diagnosis can never
drift out of sync.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from agent_brain_cli.config import (
    LEGACY_STATE_DIR_NAME,
    STATE_DIR_NAME,
    get_server_url,
    load_config,
    resolve_project_root,
)

#: Severity returned by every diagnostic check.
SEVERITY_OK = "ok"
SEVERITY_WARN = "warn"
SEVERITY_FAIL = "fail"

DOCTOR_HINT = "Tip: run `agent-brain doctor` to diagnose your setup."


@dataclass
class CheckResult:
    """One row in the doctor output."""

    name: str
    status: str  # ok | warn | fail
    message: str
    fix: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DoctorReport:
    """The full diagnostic snapshot."""

    project_root: str
    state_dir: str
    state_dir_exists: bool
    runtime_file: str | None
    server_url: str
    checks: list[CheckResult]

    @property
    def exit_code(self) -> int:
        """Non-zero when any critical check failed."""
        return 1 if any(c.status == SEVERITY_FAIL for c in self.checks) else 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["exit_code"] = self.exit_code
        return data


def _check_python() -> CheckResult:
    major, minor = sys.version_info[:2]
    version = f"{major}.{minor}.{sys.version_info.micro}"
    if (major, minor) >= (3, 10):
        return CheckResult(
            "python_version",
            SEVERITY_OK,
            f"Python {version}",
            details={"version": version},
        )
    return CheckResult(
        "python_version",
        SEVERITY_FAIL,
        f"Python {version} — Agent Brain requires 3.10+",
        fix="Upgrade to Python 3.10 or newer.",
        details={"version": version},
    )


def _check_project_init(project_root: Path, state_dir: Path) -> CheckResult:
    config_path = state_dir / "config.json"
    if config_path.exists():
        return CheckResult(
            "project_initialized",
            SEVERITY_OK,
            f"Project initialized at {state_dir}",
            details={"state_dir": str(state_dir)},
        )
    return CheckResult(
        "project_initialized",
        SEVERITY_FAIL,
        f"No {STATE_DIR_NAME}/config.json under {project_root}",
        fix="Run `agent-brain init` in your project directory.",
        details={
            "project_root": str(project_root),
            "expected_path": str(config_path),
        },
    )


def _check_provider_config(state_dir: Path) -> CheckResult:
    yaml_path = state_dir / "config.yaml"
    try:
        cfg = load_config()
    except Exception as exc:  # pragma: no cover — pydantic noise
        return CheckResult(
            "provider_config",
            SEVERITY_FAIL,
            f"Failed to load config.yaml: {exc}",
            fix=f"Fix or delete {yaml_path} and re-run `agent-brain doctor`.",
        )

    return CheckResult(
        "provider_config",
        SEVERITY_OK,
        (
            f"embedding={cfg.embedding.provider}:{cfg.embedding.model}, "
            f"summarization={cfg.summarization.provider}:{cfg.summarization.model}"
        ),
        details={
            "config_path": str(yaml_path) if yaml_path.exists() else None,
            "embedding_provider": cfg.embedding.provider,
            "embedding_model": cfg.embedding.model,
            "summarization_provider": cfg.summarization.provider,
            "summarization_model": cfg.summarization.model,
        },
    )


_PROVIDER_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "cohere": "COHERE_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "grok": "XAI_API_KEY",
}


def _check_api_keys() -> list[CheckResult]:
    try:
        cfg = load_config()
    except Exception:  # pragma: no cover
        return []

    results: list[CheckResult] = []
    for label, provider, model in (
        ("embedding", cfg.embedding.provider, cfg.embedding.model),
        ("summarization", cfg.summarization.provider, cfg.summarization.model),
    ):
        if provider == "ollama":
            continue
        env_name = (
            cfg.embedding.api_key_env
            if label == "embedding"
            else cfg.summarization.api_key_env
        ) or _PROVIDER_KEY_ENV.get(provider.lower())
        if not env_name:
            continue
        present = bool(os.environ.get(env_name))
        results.append(
            CheckResult(
                f"api_key_{label}",
                SEVERITY_OK if present else SEVERITY_FAIL,
                (
                    f"{env_name} is set"
                    if present
                    else f"{env_name} is not set (required by {provider})"
                ),
                fix=(
                    None
                    if present
                    else f"export {env_name}=… then re-run `agent-brain doctor`."
                ),
                details={
                    "provider": provider,
                    "model": model,
                    "env_var": env_name,
                    "present": present,
                },
            )
        )
    return results


def _is_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def _check_server(server_url: str, runtime_file: Path | None) -> CheckResult:
    if runtime_file and not runtime_file.exists():
        return CheckResult(
            "server_reachable",
            SEVERITY_WARN,
            (
                f"No runtime.json at {runtime_file} — server is probably not "
                "running for this project."
            ),
            fix="Run `agent-brain start` to launch the server.",
            details={
                "runtime_file": str(runtime_file),
                "server_url": server_url,
            },
        )

    try:
        req = Request(server_url.rstrip("/") + "/health")
        with urlopen(req, timeout=3) as resp:  # noqa: S310 — local URL
            body = resp.read().decode("utf-8", errors="replace")
        return CheckResult(
            "server_reachable",
            SEVERITY_OK,
            f"Server responded at {server_url}",
            details={"server_url": server_url, "response_preview": body[:120]},
        )
    except URLError as exc:
        return CheckResult(
            "server_reachable",
            SEVERITY_FAIL,
            f"Cannot reach server at {server_url}: {exc.reason}",
            fix="Start it with `agent-brain start` (or pass --url).",
            details={"server_url": server_url, "error": str(exc.reason)},
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "server_reachable",
            SEVERITY_FAIL,
            f"Error contacting server at {server_url}: {exc}",
            fix="Start it with `agent-brain start` (or pass --url).",
            details={"server_url": server_url, "error": str(exc)},
        )


def _check_optional_dep(provider: str, module_name: str, extra: str) -> CheckResult:
    """Report on an optional Python package that a chosen provider needs."""
    if shutil.which("python3"):
        # We import in-process so test mocks of installed packages work.
        try:
            __import__(module_name)
            return CheckResult(
                f"optional_dep_{module_name}",
                SEVERITY_OK,
                f"{module_name} is installed ({provider} provider)",
                details={"module": module_name, "provider": provider},
            )
        except ImportError:
            return CheckResult(
                f"optional_dep_{module_name}",
                SEVERITY_FAIL,
                (
                    f"{provider} provider selected but {module_name} is not "
                    "installed."
                ),
                fix=f"pip install 'agent-brain-rag[{extra}]'",
                details={
                    "module": module_name,
                    "provider": provider,
                    "extras_install": extra,
                },
            )
    return CheckResult(
        f"optional_dep_{module_name}",
        SEVERITY_WARN,
        "Could not run Python interpreter to verify imports.",
    )


def _check_gitignore(project_root: Path) -> CheckResult:
    gi = project_root / ".gitignore"
    if not gi.exists():
        return CheckResult(
            "gitignore_state_dir",
            SEVERITY_WARN,
            f"No .gitignore at {project_root} — {STATE_DIR_NAME}/ may get committed.",
            fix=f"Add `{STATE_DIR_NAME}/` to .gitignore.",
        )
    try:
        lines = {line.strip() for line in gi.read_text().splitlines()}
    except OSError:
        return CheckResult(
            "gitignore_state_dir",
            SEVERITY_WARN,
            f"Could not read {gi}.",
        )
    if any(entry in lines for entry in (STATE_DIR_NAME, f"{STATE_DIR_NAME}/")):
        return CheckResult(
            "gitignore_state_dir",
            SEVERITY_OK,
            f"{STATE_DIR_NAME}/ is in .gitignore",
        )
    return CheckResult(
        "gitignore_state_dir",
        SEVERITY_WARN,
        f"{STATE_DIR_NAME}/ is not in .gitignore — index data may get committed.",
        fix=f"Add `{STATE_DIR_NAME}/` to .gitignore.",
    )


def run_doctor(server_url_override: str | None = None) -> DoctorReport:
    """Run every check and return a structured report."""
    project_root = resolve_project_root()
    state_dir = project_root / STATE_DIR_NAME
    runtime_file: Path | None
    if state_dir.exists():
        runtime_file = state_dir / "runtime.json"
    else:
        legacy = project_root / LEGACY_STATE_DIR_NAME
        runtime_file = legacy / "runtime.json" if legacy.exists() else None

    server_url = server_url_override or get_server_url()

    checks: list[CheckResult] = []
    checks.append(_check_python())
    checks.append(_check_project_init(project_root, state_dir))
    checks.append(_check_provider_config(state_dir))
    checks.extend(_check_api_keys())

    # Optional deps that surface common install failures (issues #122/#125/#129).
    try:
        cfg = load_config()
    except Exception:  # pragma: no cover
        cfg = None
    if cfg and cfg.embedding.provider.lower() == "cohere":
        checks.append(_check_optional_dep("cohere", "cohere", "cohere"))
    checks.append(_check_gitignore(project_root))

    checks.append(_check_server(server_url, runtime_file))

    return DoctorReport(
        project_root=str(project_root),
        state_dir=str(state_dir),
        state_dir_exists=state_dir.exists(),
        runtime_file=str(runtime_file) if runtime_file else None,
        server_url=server_url,
        checks=checks,
    )


def doctor_hint_message(project_root: Path | None = None) -> str:
    """Suggest the doctor command — and call out the most likely setup issue.

    When ``runtime.json`` is missing, the user almost certainly hasn't run
    ``agent-brain init && agent-brain start`` in this directory. Saying so
    is more useful than the generic "connection refused".
    """
    root = project_root or resolve_project_root()
    state_dir = root / STATE_DIR_NAME
    runtime_file = state_dir / "runtime.json"
    if not runtime_file.exists():
        return (
            "Tip: no `.agent-brain/runtime.json` found under "
            f"{root}. Run `agent-brain init` and `agent-brain start` here "
            "first, or run `agent-brain doctor` to diagnose."
        )
    return DOCTOR_HINT


def report_to_json(report: DoctorReport) -> str:
    return json.dumps(report.to_dict(), indent=2)


def env_snapshot() -> dict[str, Any]:
    """Lightweight environment summary used in JSON output."""
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cwd": str(Path.cwd()),
    }
