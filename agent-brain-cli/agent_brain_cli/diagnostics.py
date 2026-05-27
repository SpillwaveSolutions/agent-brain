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
    resolve_project_root_with_strategy,
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


_RESOLVE_STRATEGY_LABEL: dict[str, str] = {
    "agent_brain_dir": f"found {STATE_DIR_NAME}/ in this dir or an ancestor",
    "legacy_claude_dir": f"found legacy {LEGACY_STATE_DIR_NAME}/",
    "git_root": "git repository root (no state dir present yet)",
    "claude_dir": ".claude/ marker in this dir or an ancestor",
    "pyproject": "pyproject.toml marker in this dir or an ancestor",
    "cwd_fallback": "no markers found — falling back to cwd",
}


def _check_version() -> CheckResult:
    """Confirm the installed agent-brain-cli is importable and report version.

    Issue #146 check #2 — surfaces broken installs (missing entry-point,
    namespace shadowing, half-rolled-back upgrades) at the top of the doctor
    report instead of leaving the user to discover them later.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version

        ver = version("agent-brain-cli")
    except PackageNotFoundError as exc:
        return CheckResult(
            "cli_version",
            SEVERITY_FAIL,
            "agent-brain-cli is not installed in this Python environment.",
            fix="pip install agent-brain-cli  (or uv tool install agent-brain-cli)",
            details={"error": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "cli_version",
            SEVERITY_FAIL,
            f"Could not determine agent-brain-cli version: {exc}",
        )
    return CheckResult(
        "cli_version",
        SEVERITY_OK,
        f"agent-brain-cli {ver}",
        details={"version": ver},
    )


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


def _check_project_init(
    project_root: Path, state_dir: Path, resolved_via: str
) -> CheckResult:
    """Validate the resolved project root and explain *why* it was picked.

    Issue #146 check #3 — operators on monorepos / nested projects can be
    surprised by which directory wins; the strategy label tells them.
    """
    strategy_msg = _RESOLVE_STRATEGY_LABEL.get(resolved_via, resolved_via)
    config_path = state_dir / "config.json"
    if config_path.exists():
        return CheckResult(
            "project_initialized",
            SEVERITY_OK,
            f"Project initialized at {state_dir} ({strategy_msg})",
            details={
                "state_dir": str(state_dir),
                "resolved_via": resolved_via,
            },
        )
    return CheckResult(
        "project_initialized",
        SEVERITY_FAIL,
        (f"No {STATE_DIR_NAME}/config.json under {project_root} " f"({strategy_msg})"),
        fix="Run `agent-brain init` in your project directory.",
        details={
            "project_root": str(project_root),
            "expected_path": str(config_path),
            "resolved_via": resolved_via,
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
        # Issue #146 check #7 — also pull /health/status for the richer
        # indexing summary. Tolerate older servers that 404 here.
        indexing_summary, indexing_payload = _fetch_indexing_summary(server_url)
        message = f"Server responded at {server_url}"
        if indexing_summary:
            message = f"{message} — {indexing_summary}"
        return CheckResult(
            "server_reachable",
            SEVERITY_OK,
            message,
            details={
                "server_url": server_url,
                "response_preview": body[:120],
                "indexing": indexing_payload,
            },
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


def _fetch_indexing_summary(
    server_url: str,
) -> tuple[str | None, dict[str, Any] | None]:
    """Best-effort fetch of /health/status, returning (one-line summary, raw)."""
    try:
        req = Request(server_url.rstrip("/") + "/health/status")
        with urlopen(req, timeout=3) as resp:  # noqa: S310 — local URL
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001 — old server or transient error is fine
        return None, None
    if not isinstance(payload, dict):
        return None, None
    state = payload.get("state") or payload.get("indexing_state") or "unknown"
    chunk_count = (
        payload.get("chunk_count")
        or payload.get("total_chunks")
        or payload.get("document_count")
    )
    parts = [f"indexing={state}"]
    if isinstance(chunk_count, int):
        parts.append(f"chunks={chunk_count}")
    return ", ".join(parts), payload


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


def _graph_index_dir(state_dir: Path) -> Path:
    """Return the conventional graph_index location under a state dir."""
    return state_dir / "data" / "graph_index"


def _read_graphrag_block(state_dir: Path) -> dict[str, Any] | None:
    """Read the ``graphrag`` block from the project's config.yaml, if any.

    The CLI's Pydantic ``AgentBrainConfig`` doesn't model graphrag (it's a
    server concern), so this peeks directly at the YAML. Returns None when
    no graphrag block is present.
    """
    import yaml  # local import to avoid a hard dep at module load

    for name in ("config.yaml", "agent-brain.yaml", "config.yml"):
        path = state_dir / name
        if not path.exists():
            continue
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except (OSError, yaml.YAMLError):
            continue
        block = data.get("graphrag")
        if isinstance(block, dict):
            return block
    return None


def _check_graph_store_health(state_dir: Path) -> CheckResult | None:
    """Verify the Kuzu DB opens cleanly when GraphRAG is enabled (Issue #166).

    Returns None when GraphRAG is disabled or the store backend isn't Kuzu —
    those cases have no graph health to report. Otherwise opens the Kuzu DB
    in process briefly. A successful open is OK. An IndexError / RuntimeError
    (the typical kill-mid-write signature) is FAIL with a fix hint pointing
    at ``--fix`` or manual recovery.
    """
    block = _read_graphrag_block(state_dir)
    if not block or not block.get("enabled"):
        return None
    store_type = str(block.get("store_type") or "simple").lower()
    if store_type != "kuzu":
        return None

    graph_dir = _graph_index_dir(state_dir)
    kuzu_db_path = graph_dir / "kuzu_db"
    if not kuzu_db_path.exists():
        # Nothing on disk yet — nothing to be corrupted.
        return CheckResult(
            "graph_store_health",
            SEVERITY_OK,
            f"No Kuzu DB on disk yet at {kuzu_db_path} (will be created on "
            "first indexing job).",
            details={"path": str(kuzu_db_path)},
        )

    try:
        import kuzu
    except ImportError:
        # The langextract optional-dep check already covers missing extras.
        return None

    try:
        kuzu.Database(str(kuzu_db_path))
    except (IndexError, RuntimeError) as exc:
        return CheckResult(
            "graph_store_health",
            SEVERITY_FAIL,
            f"Kuzu DB at {kuzu_db_path} appears corrupted: {exc}. This "
            "typically happens when the server was killed mid-indexing.",
            fix=(
                "Run `agent-brain doctor --fix` (server must be stopped) to "
                "quarantine the corrupted file and restore from the latest "
                "snapshot, or manually `rm` the file (loses all triplets)."
            ),
            details={"path": str(kuzu_db_path), "error": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001 — anything unexpected
        return CheckResult(
            "graph_store_health",
            SEVERITY_WARN,
            f"Could not check Kuzu DB at {kuzu_db_path}: {exc}",
        )

    return CheckResult(
        "graph_store_health",
        SEVERITY_OK,
        f"Kuzu DB at {kuzu_db_path} opens cleanly.",
        details={"path": str(kuzu_db_path)},
    )


def _server_is_running(state_dir: Path) -> bool:
    """Best-effort check for an active server lock under state_dir."""
    return (state_dir / "server.lock").exists() or (state_dir / "lock").exists()


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
    project_root, resolved_via = resolve_project_root_with_strategy()
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
    checks.append(_check_version())
    checks.append(_check_project_init(project_root, state_dir, resolved_via))
    checks.append(_check_provider_config(state_dir))
    checks.extend(_check_api_keys())

    # Optional deps that surface common install failures (issues #122/#125/#129).
    try:
        cfg = load_config()
    except Exception:  # pragma: no cover
        cfg = None
    if cfg and cfg.embedding.provider.lower() == "cohere":
        checks.append(_check_optional_dep("cohere", "cohere", "cohere"))

    # Issue #146 check #8 — surface graphrag's langextract dependency.
    if cfg and getattr(getattr(cfg, "graphrag", None), "enabled", False):
        checks.append(
            _check_optional_dep("graphrag (langextract)", "langextract", "graphrag")
        )

    # Issue #166 — verify Kuzu DB opens cleanly.
    graph_check = _check_graph_store_health(state_dir)
    if graph_check is not None:
        checks.append(graph_check)

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


def apply_safe_fixes(report: DoctorReport) -> list[str]:
    """Apply the subset of fixes that are safe + idempotent + offline.

    Returns the list of human-readable actions taken (empty if nothing to fix).
    Used by ``agent-brain doctor --fix``. Anything that calls the network,
    modifies user code, or requires an API key is *not* covered here — the
    user must still address those manually.
    """
    actions: list[str] = []
    project_root = Path(report.project_root)
    state_dir = Path(report.state_dir)
    for check in report.checks:
        if check.name == "gitignore_state_dir" and check.status != SEVERITY_OK:
            gi = project_root / ".gitignore"
            line = f"{STATE_DIR_NAME}/\n"
            if gi.exists():
                content = gi.read_text()
                if not content.endswith("\n"):
                    content += "\n"
                gi.write_text(content + line)
            else:
                gi.write_text(line)
            actions.append(f"Added {STATE_DIR_NAME}/ to {gi}.")
        elif check.name == "project_initialized" and check.status == SEVERITY_FAIL:
            # Create the state dir + a minimal config.json shell so a follow-up
            # `agent-brain init` (or any command) has something to read.
            state_dir.mkdir(parents=True, exist_ok=True)
            cfg_json = state_dir / "config.json"
            if not cfg_json.exists():
                cfg_json.write_text(
                    json.dumps(
                        {
                            "project_root": str(project_root),
                            "created_by": "agent-brain doctor --fix",
                        },
                        indent=2,
                    )
                    + "\n"
                )
                actions.append(f"Created {cfg_json}.")
        elif check.name == "graph_store_health" and check.status == SEVERITY_FAIL:
            # Issue #166 — recover a corrupted Kuzu DB offline.
            if _server_is_running(state_dir):
                actions.append(
                    "Skipped Kuzu recovery: server appears to be running. "
                    "Stop it with `agent-brain stop` first, then re-run "
                    "`agent-brain doctor --fix`."
                )
                continue
            graph_dir = _graph_index_dir(state_dir)
            kuzu_db = graph_dir / "kuzu_db"
            kuzu_wal = graph_dir / "kuzu_db.wal"
            stamp = _utc_stamp()
            for src in (kuzu_db, kuzu_wal):
                if src.exists():
                    dest = src.with_name(f"{src.name}.corrupted-{stamp}")
                    src.rename(dest)
                    actions.append(
                        f"Quarantined {src.name} → {dest.name} "
                        "(forensic preservation)."
                    )
            # Restore from latest snapshot, if one exists.
            restored = _replay_latest_snapshot(graph_dir)
            if restored is not None:
                snapshot_name, count = restored
                actions.append(
                    f"Restored {count} triplets from snapshot "
                    f"{snapshot_name} into a fresh Kuzu DB."
                )
            else:
                actions.append(
                    "No snapshot available to restore; graph index will "
                    "start empty. Re-run `agent-brain index <folder>` to "
                    "rebuild."
                )
    return actions


def _utc_stamp() -> str:
    """Filesystem-safe UTC timestamp suffix shared with the server's
    quarantine logic (graph_store._corrupted_sibling)."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _replay_latest_snapshot(graph_dir: Path) -> tuple[str, int] | None:
    """Replay triplets from the newest valid snapshot into a fresh Kuzu DB.

    Returns ``(snapshot_filename, triplet_count)`` on success, or ``None`` if
    there's no usable snapshot. Best-effort: any failure becomes a None
    return (the caller will report it). The CLI doesn't import the server
    code path because the CLI may be installed without the server package;
    instead it reads snapshot JSON directly using a minimal schema.
    """
    snap_dir = graph_dir / "snapshots"
    if not snap_dir.is_dir():
        return None
    try:
        import kuzu
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from llama_index.graph_stores.kuzu import KuzuPropertyGraphStore
    except ImportError:
        return None

    candidates = sorted(
        (p for p in snap_dir.iterdir() if p.is_file() and p.suffix == ".json"),
        key=lambda p: (p.stat().st_mtime, p.name),
        reverse=True,
    )
    for snap in candidates:
        try:
            payload = json.loads(snap.read_text())
            if payload.get("schema_version") != 1:
                continue
            triplets = payload.get("triplets") or []
        except (OSError, json.JSONDecodeError):
            continue

        try:
            db = kuzu.Database(str(graph_dir / "kuzu_db"))
            store = KuzuPropertyGraphStore(db, use_vector_index=False)
            for t in triplets:
                subj = EntityNode(
                    name=t["subject"],
                    label=t.get("subject_type") or "Entity",
                )
                obj = EntityNode(
                    name=t["object"],
                    label=t.get("object_type") or "Entity",
                )
                store.upsert_nodes([subj, obj])
                store.upsert_relations(
                    [
                        Relation(
                            label=t["predicate"],
                            source_id=subj.id,
                            target_id=obj.id,
                            properties=(
                                {"source_chunk_id": t["source_chunk_id"]}
                                if t.get("source_chunk_id")
                                else {}
                            ),
                        )
                    ]
                )
            return snap.name, len(triplets)
        except Exception:  # noqa: BLE001
            # If replay against this snapshot failed, try the next-older.
            continue
    return None


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
