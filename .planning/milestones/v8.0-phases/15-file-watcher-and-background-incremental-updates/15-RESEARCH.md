# Phase 15: File Watcher & Background Incremental Updates - Research

**Researched:** 2026-03-06
**Domain:** watchfiles async file watching, asyncio per-folder task pattern, job queue integration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Watcher Config Model:**
- Extend FolderRecord dataclass with `watch_mode: str = "off"` and `watch_debounce_seconds: int | None = None` fields
- Persisted in existing `indexed_folders.jsonl` — single source of truth for all folder config
- Global default debounce (30 seconds) in config.yaml, with per-folder override via `watch_debounce_seconds`
- Default watch_mode for new folders is `off` (explicit opt-in) — no surprise behavior

**CLI Surface:**
- `--watch` and `--debounce` flags added to the existing `agent-brain folders add` command
- Usage: `agent-brain folders add ./src --watch auto --debounce 10`
- Consistent with existing `--include-type` pattern on folders add
- No separate `agent-brain folders watch` command — all config via flags on `folders add`

**Job Source Tracking:**
- New `source: str` field on JobRecord Pydantic model with values `"manual"` or `"auto"`
- Default `"manual"` preserves backward compatibility with existing jobs
- Source column added to `agent-brain jobs` table output
- Debounce + existing dedupe_key deduplication is sufficient — no additional rate limiting
- Auto and manual jobs cancel identically — no special bulk cancel for auto jobs

### Claude's Discretion

- Exclusion patterns for watcher (.git/, __pycache__/, dist/, build/, node_modules/) — hardcoded sensible defaults
- Watcher lifecycle: start watching on server boot for all auto folders, stop when folder removed
- watchfiles `awatch()` usage pattern including stop_event for graceful shutdown
- Error handling for watcher failures (log and continue, don't crash server)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 15 adds a `FileWatcherService` that monitors folders registered with `watch_mode: auto` and automatically enqueues incremental reindex jobs when files change. The implementation uses `watchfiles.awatch()` — already installed as a transitive dependency via `uvicorn[standard]` — which provides a native async generator interface that eliminates all thread-boundary complexity. The per-folder task pattern (one `asyncio.Task` per watched folder, each running its own `awatch()` loop) gives independent per-folder debounce without any shared timer state.

The `watchfiles` `DefaultFilter` already excludes `.git/`, `__pycache__/`, `node_modules/`, `.venv/`, `.mypy_cache/`, `.pytest_cache/`, `.pyc` files, and `.DS_Store` — matching the exclusion requirements exactly. The `debounce` parameter on `awatch()` is in milliseconds (default 1600ms) and handles batching per `async for` yield. The `stop_event` parameter accepts an `anyio.Event`, which works correctly inside FastAPI's asyncio event loop. Both facts are verified by running the actual library.

The primary extension points are narrow: extend `FolderRecord` dataclass with two new fields (backward-compatible via `data.get()` in `_load_jsonl`), add `source: str` to `JobRecord` Pydantic model, and add `FileWatcherService` to the lifespan alongside the existing `_job_worker` pattern. No changes to `IndexingService`, `ManifestTracker`, `JobWorker`, or any storage layer.

**Primary recommendation:** Use one `asyncio.Task` per watched folder, each running `watchfiles.awatch(path, debounce=debounce_ms, stop_event=folder_stop_event)`. Shared `anyio.Event` on `FileWatcherService.stop()` signals all per-folder tasks to exit cleanly.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `watchfiles` | 1.1.1 (already installed) | Async file system watching | Rust-backed via `notify` crate; native `async for` interface; already a transitive dep via `uvicorn[standard]`; verified working in this project's venv |
| `anyio` | already installed | `anyio.Event` for `stop_event` | Required by `watchfiles.awatch()` `stop_event` parameter; already installed as transitive dep |

### No New Dependencies Required

`watchfiles` is **already installed** as a transitive dependency via `uvicorn[standard]`. Verified via:

```
poetry show watchfiles
  name         : watchfiles
  version      : 1.1.1
  required by  : uvicorn requires >=0.13
```

`anyio` is likewise already present. Zero new production dependencies needed for Phase 15.

### What NOT to Use

| Alternative | Why Not |
|------------|---------|
| `watchdog` | Requires threading bridge (`call_soon_threadsafe`) — eliminated by using `watchfiles` native `async for` |
| Per-folder `threading.Timer` debounce | Over-engineering — `watchfiles.awatch(debounce=N)` handles batching at the Rust level |
| Global `asyncio.Queue` bridge pattern | Unnecessary — per-folder `async for` tasks eliminate the shared queue entirely |

---

## Architecture Patterns

### Recommended Project Structure (New and Modified Files)

```
agent-brain-server/
└── agent_brain_server/
    ├── services/
    │   ├── file_watcher_service.py    # NEW: FileWatcherService
    │   └── folder_manager.py          # MODIFY: extend FolderRecord dataclass
    ├── models/
    │   ├── job.py                     # MODIFY: add source field to JobRecord + JobSummary
    │   └── folders.py                 # MODIFY: add watch_mode/debounce to FolderInfo
    ├── job_queue/
    │   └── job_service.py             # MODIFY: enqueue_job() accepts source param
    ├── api/
    │   ├── main.py                    # MODIFY: lifespan wires FileWatcherService
    │   └── routers/
    │       └── folders.py             # MODIFY: expose watch_mode in list response
    └── config/
        └── settings.py                # MODIFY: add AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS
agent-brain-cli/
└── agent_brain_cli/
    └── commands/
        ├── folders.py                 # MODIFY: --watch and --debounce flags on 'add'
        └── jobs.py                    # MODIFY: Source column in jobs table
agent-brain-plugin/
└── skills/
    └── using-agent-brain/
        └── references/
            └── api_reference.md       # MODIFY: document watch_mode in folder commands
```

### Pattern 1: Per-Folder asyncio Task with watchfiles.awatch()

**What:** Each watched folder gets its own `asyncio.Task` running `watchfiles.awatch()`. The task loops `async for`, and when changes arrive, checks for an existing pending/running job before enqueuing a new one.

**When to use:** Always — this is the only pattern. One task per folder = independent debounce timers, no shared state, clean cancellation.

**Verified working:** Tested in the project venv against watchfiles 1.1.1.

```python
# Source: verified in agent-brain-server venv (watchfiles 1.1.1)
import asyncio
import anyio
import watchfiles
from watchfiles import Change

async def _watch_folder(
    folder_path: str,
    debounce_ms: int,
    stop_event: anyio.Event,
    enqueue_callback: "Callable[[str], Awaitable[None]]",
) -> None:
    """Watch a single folder and enqueue reindex jobs on change.

    Uses watchfiles.awatch() which:
    - Runs a Rust-backed watcher in a thread pool
    - Batches all events within the debounce window into a single yield
    - Stops cleanly when stop_event is set
    - DefaultFilter already excludes .git/, __pycache__/, node_modules/, .venv/
    """
    try:
        async for changes in watchfiles.awatch(
            folder_path,
            debounce=debounce_ms,       # milliseconds — convert from seconds
            stop_event=stop_event,
            recursive=True,
        ):
            # changes is a set of (Change, str) tuples — batch already collapsed
            if changes:
                await enqueue_callback(folder_path)
    except Exception as e:
        # Log and continue — watcher failure must not crash server
        import logging
        logging.getLogger(__name__).error(
            f"Watcher error for {folder_path}: {e}", exc_info=True
        )
```

### Pattern 2: FileWatcherService Lifecycle (mirrors JobWorker pattern)

**What:** Module-level `_file_watcher` ref in `api/main.py`, initialized in lifespan after `_job_worker.start()`, torn down before `_job_worker.stop()`.

**When to use:** This is the established pattern in the codebase — `_job_worker` follows this exact pattern today.

```python
# Source: api/main.py lifespan additions (follows existing _job_worker pattern)
# In lifespan startup — after _job_worker.start():
from agent_brain_server.services.file_watcher_service import FileWatcherService

_file_watcher = FileWatcherService(
    folder_manager=folder_manager,
    job_service=job_service,
    default_debounce_seconds=settings.AGENT_BRAIN_WATCH_DEBOUNCE_SECONDS,
)
await _file_watcher.start()
app.state.file_watcher_service = _file_watcher

# In lifespan shutdown — BEFORE _job_worker.stop():
if _file_watcher is not None:
    await _file_watcher.stop()
```

### Pattern 3: FolderRecord Backward-Compatible Extension

**What:** Add `watch_mode: str = "off"` and `watch_debounce_seconds: int | None = None` to the `FolderRecord` dataclass. Update `_load_jsonl` to use `data.get()` with defaults. Existing JSONL files load without error.

**Critical:** `FolderRecord` is currently a `dataclass`, not a Pydantic model. Keep it as a dataclass — do NOT switch to Pydantic here as `asdict()` is used in `_write_jsonl`.

```python
# Source: agent_brain_server/services/folder_manager.py (MODIFY)
@dataclass
class FolderRecord:
    folder_path: str
    chunk_count: int
    last_indexed: str
    chunk_ids: list[str]
    # NEW — defaults ensure v7.0 JSONL files load without KeyError
    watch_mode: str = "off"
    watch_debounce_seconds: int | None = None
```

`_load_jsonl` must change from `data["key"]` to `data.get("key", default)`:

```python
# Source: agent_brain_server/services/folder_manager.py (MODIFY _load_jsonl)
record = FolderRecord(
    folder_path=data["folder_path"],     # required, no default
    chunk_count=data["chunk_count"],     # required, no default
    last_indexed=data["last_indexed"],   # required, no default
    chunk_ids=data["chunk_ids"],         # required, no default
    watch_mode=data.get("watch_mode", "off"),
    watch_debounce_seconds=data.get("watch_debounce_seconds", None),
)
```

### Pattern 4: JobRecord source Field (Backward-Compatible Extension)

**What:** Add `source: str = "manual"` to `JobRecord`. Update `JobSummary` and `JobDetailResponse` to include it. The `source` column appears in `agent-brain jobs` table output.

```python
# Source: agent_brain_server/models/job.py (MODIFY JobRecord)
class JobRecord(BaseModel):
    # ... existing fields ...
    source: str = Field(
        default="manual",
        description="Job source: 'manual' (user-triggered) or 'auto' (watcher-triggered)",
    )
```

Serialized to JSONL via Pydantic's `.model_dump()` — the `source` field appears in JSON. Existing JSONL records missing `source` load with default `"manual"` via Pydantic's default handling.

`enqueue_job()` in `JobQueueService` must accept `source: str = "manual"` and pass it to `JobRecord` creation.

### Pattern 5: Watcher-to-JobService Integration

**What:** `FileWatcherService._consume_folder()` calls `job_service.enqueue_job()` with `source="auto"` and `force=False`. The existing `dedupe_key` mechanism prevents enqueueing a duplicate job if one is already PENDING/RUNNING for the same folder.

```python
# Source: services/file_watcher_service.py (NEW)
async def _enqueue_for_folder(self, folder_path: str) -> None:
    """Enqueue an auto-triggered incremental reindex job."""
    from agent_brain_server.models import IndexRequest

    request = IndexRequest(
        folder_path=folder_path,
        include_code=True,  # Preserve code indexing setting
        recursive=True,
        force=False,        # CRITICAL: use ManifestTracker incremental diff
    )
    try:
        result = await self._job_service.enqueue_job(
            request=request,
            operation="index",
            force=False,    # force=False enables dedupe check
            source="auto",  # NEW field — marks as watcher-triggered
        )
        if result.dedupe_hit:
            logger.debug(
                f"Auto-reindex skipped (existing job {result.job_id}): {folder_path}"
            )
        else:
            logger.info(f"Auto-reindex queued ({result.job_id}): {folder_path}")
    except Exception as e:
        logger.error(f"Failed to enqueue auto-reindex for {folder_path}: {e}")
```

### Pattern 6: FileWatcherService.stop() with anyio.Event

**What:** A single shared `anyio.Event` signals all per-folder tasks to stop. `stop()` sets the event, then awaits all tasks to complete.

**Verified:** `anyio.Event` must be created inside an async context (after the asyncio event loop is running). Create it in `start()`, not in `__init__()`.

```python
# Source: services/file_watcher_service.py (NEW)
class FileWatcherService:
    def __init__(
        self,
        folder_manager: FolderManager,
        job_service: JobQueueService,
        default_debounce_seconds: int = 30,
    ) -> None:
        self._folder_manager = folder_manager
        self._job_service = job_service
        self._default_debounce_seconds = default_debounce_seconds
        # NOTE: _stop_event must be created in start(), not here
        # anyio.Event requires an async context (asyncio loop must be running)
        self._stop_event: anyio.Event | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        """Start watching all auto-mode folders. Call in lifespan."""
        self._stop_event = anyio.Event()  # Created inside async context — correct
        folders = await self._folder_manager.list_folders()
        for record in folders:
            if record.watch_mode == "auto":
                self._start_folder_task(record.folder_path, record.watch_debounce_seconds)
        logger.info(f"FileWatcherService started ({len(self._tasks)} folders)")

    async def stop(self) -> None:
        """Stop all folder watchers. Call in lifespan shutdown."""
        if self._stop_event is not None:
            self._stop_event.set()
        # Cancel and await all tasks
        for path, task in list(self._tasks.items()):
            task.cancel()
        for path, task in list(self._tasks.items()):
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        logger.info("FileWatcherService stopped")

    def _start_folder_task(
        self, folder_path: str, debounce_seconds: int | None
    ) -> None:
        """Start a watcher task for one folder."""
        debounce_ms = (
            (debounce_seconds or self._default_debounce_seconds) * 1000
        )
        task = asyncio.create_task(
            _watch_folder(
                folder_path=folder_path,
                debounce_ms=debounce_ms,
                stop_event=self._stop_event,
                enqueue_callback=self._enqueue_for_folder,
            ),
            name=f"watcher-{folder_path}",
        )
        self._tasks[folder_path] = task

    def add_folder_watch(self, folder_path: str, debounce_seconds: int | None) -> None:
        """Called after folder added with watch_mode='auto'. No-op if already watching."""
        if folder_path in self._tasks:
            return
        if self._stop_event is None:
            logger.warning(f"FileWatcherService not started, cannot watch {folder_path}")
            return
        self._start_folder_task(folder_path, debounce_seconds)
        logger.info(f"Started watching {folder_path}")

    def remove_folder_watch(self, folder_path: str) -> None:
        """Called when folder removed or watch_mode changed to 'off'."""
        task = self._tasks.pop(folder_path, None)
        if task is not None:
            task.cancel()
            logger.info(f"Stopped watching {folder_path}")
```

### Anti-Patterns to Avoid

- **Using `watchdog` library:** Requires threading bridge. `watchfiles` is already installed and eliminates the problem entirely.
- **Per-file debounce:** `watchfiles.awatch()` debounces at the Rust level per path — all events in the window collapse to one yield. Never implement additional per-file timers.
- **Calling `asyncio.create_task()` from a thread:** Not applicable with `watchfiles` native `async for`, but never do this.
- **Creating `anyio.Event()` in `__init__()`:** Fails outside async context. Always create in `start()` or another `async` method.
- **`force=True` for watcher jobs:** Bypasses `ManifestTracker`, re-embeds all chunks on every file change. Always `force=False`.
- **Direct `IndexingService` calls from watcher:** Bypasses job queue (no serialization, no timeout, no cancellation). Always route through `job_service.enqueue_job()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File change detection | OS event polling loop | `watchfiles.awatch()` | Rust-backed, uses inotify/FSEvents/kqueue natively; already installed |
| Debounce per folder | `asyncio.call_later()` cancel-restart pattern | `watchfiles.awatch(debounce=N)` | Batching is done at Rust level inside `awatch()`; the per-yield set already contains all events from the window |
| Thread-to-asyncio bridge | `asyncio.run_coroutine_threadsafe()` + queue | `watchfiles` native `async for` | Not needed at all with `watchfiles` |
| Exclusion patterns | Custom filter logic | `watchfiles.DefaultFilter` | Already excludes `.git/`, `__pycache__/`, `node_modules/`, `.venv/`, `.pyc`, `.DS_Store` |
| Stop mechanism | `asyncio.Event` + `cancel()` | `anyio.Event` as `stop_event` | `watchfiles.awatch()` accepts `stop_event: anyio.Event` natively; exits the `async for` cleanly when set |

**Key insight:** `watchfiles` eliminates every hand-rolled complexity that the older architecture research (ARCHITECTURE.md) described for `watchdog`. The per-folder task pattern with `awatch()` is 40-60 lines of clean async code with no thread safety concerns.

---

## Critical Discovery: watchfiles DefaultFilter Already Handles Exclusions

**HIGH confidence — verified by inspecting `watchfiles.DefaultFilter` source code in the project venv.**

`watchfiles.awatch()` uses `DefaultFilter` by default, which already ignores:

**Directories (ignore_dirs):**
- `__pycache__`
- `.git`
- `.hg`
- `.svn`
- `.tox`
- `.venv`
- `.idea`
- `node_modules`
- `.mypy_cache`
- `.pytest_cache`
- `.hypothesis`

**File patterns (ignore_entity_patterns):**
- `*.py[cod]` (compiled Python)
- `*.___jb_...___` (JetBrains temp)
- `*.sw.` (vim swapfiles)
- `*~` (editor backup)
- `.#*` (emacs lock)
- `.DS_Store`
- `flycheck_*`

The CONTEXT.md exclusion list (`.git/`, `__pycache__/`, `dist/`, `build/`, `node_modules/`) is partially covered. `dist/` and `build/` are NOT in `DefaultFilter.ignore_dirs`. These should be added as a custom filter extending `DefaultFilter` or via `ignore_paths` parameter.

**Recommended approach for Claude's Discretion (exclusions):**

```python
# Source: services/file_watcher_service.py
from watchfiles import DefaultFilter

class AgentBrainWatchFilter(DefaultFilter):
    """Extends DefaultFilter with agent-brain-specific exclusions."""

    ignore_dirs: tuple[str, ...] = (
        *DefaultFilter.ignore_dirs,
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".coverage",
        "htmlcov",
    )
```

---

## Critical Discovery: anyio.Event Must Be Created in Async Context

**HIGH confidence — verified by running `anyio.Event()` in the project venv.**

`anyio.Event()` requires a running async backend (asyncio event loop) when called. Creating it in `__init__()` fails. This is a common gotcha. Always create `self._stop_event = anyio.Event()` inside `start()` or another `async` method.

```python
# WRONG: fails at runtime
class FileWatcherService:
    def __init__(self):
        self._stop_event = anyio.Event()  # RuntimeError: no running event loop

# CORRECT: create inside async method
class FileWatcherService:
    def __init__(self):
        self._stop_event: anyio.Event | None = None  # None until start()

    async def start(self):
        self._stop_event = anyio.Event()  # asyncio loop is running here
```

---

## Critical Discovery: watchfiles debounce is in Milliseconds

**HIGH confidence — verified from `watchfiles.awatch()` signature and docs.**

The `debounce` parameter is in **milliseconds** (default 1600ms = 1.6 seconds). The user-configured debounce is in **seconds** (default 30 seconds).

Always convert:
```python
debounce_ms = debounce_seconds * 1000
# e.g., 30 seconds → 30000 milliseconds
```

A common error: passing `30` (seconds) as `debounce=30` results in 30ms debounce — effectively no debounce. A git checkout storms through in milliseconds, not in 30ms.

---

## Common Pitfalls

### Pitfall 1: anyio.Event Created Outside Async Context

**What goes wrong:** `anyio.Event()` called in `__init__()` before the event loop is running raises `RuntimeError` or `sniffio.AsyncLibraryNotFoundError`.

**Why it happens:** `anyio.Event` dispatches to the current async backend at creation time. No backend = error.

**How to avoid:** Create `anyio.Event()` in `start()` (an `async` method called from lifespan after the loop is running).

**Warning signs:** `RuntimeError: no running event loop` or `sniffio.AsyncLibraryNotFoundError` on server startup before any requests are served.

### Pitfall 2: Thundering Herd from git Checkout

**What goes wrong:** A `git checkout` or `git rebase` on a 500-file project emits 500+ events. With per-file debounce (wrong pattern), 500 jobs enqueue.

**How to avoid:** `watchfiles.awatch()` handles this automatically — the `debounce` window batches all events into one `async for` yield. The entire set of changes from the git operation arrives as one set in the loop body. One yield → one `enqueue_job()` call. The existing `dedupe_key` mechanism also prevents a second job if one is already PENDING.

**Warning signs:** Job queue depth > 1 for the same folder after git operations (indicates per-file debounce was used somewhere).

### Pitfall 3: watch_mode Stored as Freeform Data

**What goes wrong:** Using `extra` dict in `FolderRecord` for watcher config — no validation, silently uses defaults on bad input.

**How to avoid:** Add typed fields to the `FolderRecord` dataclass. Pydantic validates on load; the `asdict()` in `_write_jsonl` serializes the new fields automatically.

**Warning signs:** `watch_mode` set in CLI but watcher behavior unchanged; no error logged.

### Pitfall 4: Debounce Timer Handle Leak on Folder Removal

**What goes wrong:** Folder removed while an `awatch()` task has a pending debounce window — the task enqueues a job for a removed folder after its debounce fires.

**How to avoid:** `remove_folder_watch()` calls `task.cancel()` immediately. The `asyncio.CancelledError` from `task.cancel()` interrupts the `awatch()` generator cleanly.

**Warning signs:** Job worker logs errors for folder paths that no longer exist in folder manager.

### Pitfall 5: Watcher-Triggered Jobs Conflict with Manual --force Jobs

**What goes wrong:** A watcher job is RUNNING when a user submits a `--force` manual job. The manual job is deduped away because a job for the same folder already exists. The `force=True` flag is lost.

**How to avoid:** `force=True` in `enqueue_job()` bypasses the dedupe check entirely (see `job_service.py` line 137: `if not force:`). So `--force` from CLI correctly bypasses the watcher's existing pending job. The watcher always calls `enqueue_job(force=False)` — the dedupe check runs and returns the existing job. This is correct behavior: if a job is already running, no second job is needed.

**Warning signs:** None — this case is already handled by the existing `force` parameter logic. Document the behavior.

### Pitfall 6: include_code Setting Not Preserved in Watcher Jobs

**What goes wrong:** Watcher enqueues `IndexRequest(include_code=False)` for a folder that was originally indexed with `include_code=True`. Result: code files are dropped from the index on every auto-reindex.

**How to avoid:** `FolderRecord` should store the original indexing settings. Read `include_code` from the folder record when building the auto `IndexRequest`. This requires `add_folder()` to persist the original settings.

**Recommended approach:** Extend `FolderRecord` with `include_code: bool = False` as well, populated from the original index request. The watcher reads this to reconstruct the correct `IndexRequest`.

**Warning signs:** Code search stops returning results after first watcher-triggered reindex for a code-only folder.

---

## Code Examples

### Complete FileWatcherService

```python
# Source: services/file_watcher_service.py (NEW — verified patterns)
"""File watcher service with per-folder asyncio tasks."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Awaitable

import anyio
import watchfiles
from watchfiles import DefaultFilter

from agent_brain_server.services.folder_manager import FolderManager
from agent_brain_server.job_queue.job_service import JobQueueService
from agent_brain_server.models import IndexRequest

logger = logging.getLogger(__name__)


class AgentBrainWatchFilter(DefaultFilter):
    """Extends DefaultFilter with build output directory exclusions."""

    ignore_dirs: tuple[str, ...] = (
        *DefaultFilter.ignore_dirs,
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        "htmlcov",
    )


async def _watch_folder_loop(
    folder_path: str,
    debounce_ms: int,
    stop_event: anyio.Event,
    enqueue_callback: Callable[[str], Awaitable[None]],
) -> None:
    """Single-folder watcher loop. One asyncio.Task runs this per watched folder."""
    logger.info(f"Watcher started: {folder_path} (debounce={debounce_ms}ms)")
    try:
        async for changes in watchfiles.awatch(
            folder_path,
            debounce=debounce_ms,
            stop_event=stop_event,
            recursive=True,
            watch_filter=AgentBrainWatchFilter(),
        ):
            if changes:
                logger.debug(f"Changes in {folder_path}: {len(changes)} file(s)")
                await enqueue_callback(folder_path)
    except asyncio.CancelledError:
        logger.debug(f"Watcher task cancelled: {folder_path}")
        raise
    except Exception:
        logger.exception(f"Watcher error for {folder_path} — stopping watch")


class FileWatcherService:
    """Manages per-folder file watchers and routes changes to job queue.

    Lifecycle:
    - start(): called in FastAPI lifespan after job worker starts
    - stop(): called in FastAPI lifespan before job worker stops
    - add_folder_watch(): called after 'folders add --watch auto'
    - remove_folder_watch(): called when folder is removed
    """

    def __init__(
        self,
        folder_manager: FolderManager,
        job_service: JobQueueService,
        default_debounce_seconds: int = 30,
    ) -> None:
        self._folder_manager = folder_manager
        self._job_service = job_service
        self._default_debounce_seconds = default_debounce_seconds
        # Created in start() — anyio.Event requires async context
        self._stop_event: anyio.Event | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def watched_folder_count(self) -> int:
        """Number of currently watched folders."""
        return len(self._tasks)

    async def start(self) -> None:
        """Start watching all auto-mode folders. Call in lifespan startup."""
        self._stop_event = anyio.Event()  # Must create inside async context
        folders = await self._folder_manager.list_folders()
        for record in folders:
            if record.watch_mode == "auto":
                self._start_task(record.folder_path, record.watch_debounce_seconds)
        logger.info(
            f"FileWatcherService started, watching {len(self._tasks)} folder(s)"
        )

    async def stop(self) -> None:
        """Stop all folder watchers. Call in lifespan shutdown."""
        if self._stop_event is not None:
            self._stop_event.set()
        for task in list(self._tasks.values()):
            task.cancel()
        for task in list(self._tasks.values()):
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        logger.info("FileWatcherService stopped")

    def add_folder_watch(
        self, folder_path: str, debounce_seconds: int | None
    ) -> None:
        """Start watching a newly added auto-mode folder."""
        if folder_path in self._tasks:
            return
        if self._stop_event is None:
            logger.warning(
                f"FileWatcherService not started, cannot watch {folder_path}"
            )
            return
        self._start_task(folder_path, debounce_seconds)

    def remove_folder_watch(self, folder_path: str) -> None:
        """Stop watching a folder (removed or watch_mode changed to off)."""
        task = self._tasks.pop(folder_path, None)
        if task is not None:
            task.cancel()
            logger.info(f"Stopped watching {folder_path}")

    def _start_task(
        self, folder_path: str, debounce_seconds: int | None
    ) -> None:
        debounce_ms = (debounce_seconds or self._default_debounce_seconds) * 1000
        task = asyncio.create_task(
            _watch_folder_loop(
                folder_path=folder_path,
                debounce_ms=debounce_ms,
                stop_event=self._stop_event,  # type: ignore[arg-type]
                enqueue_callback=self._enqueue_for_folder,
            ),
            name=f"watcher:{folder_path}",
        )
        self._tasks[folder_path] = task
        logger.info(
            f"Started watching {folder_path} (debounce={debounce_ms}ms)"
        )

    async def _enqueue_for_folder(self, folder_path: str) -> None:
        """Enqueue an auto-triggered incremental reindex job."""
        # Get folder record to read original indexing settings
        record = await self._folder_manager.get_folder(folder_path)
        if record is None:
            logger.warning(f"Folder record not found for watcher event: {folder_path}")
            return

        include_code = getattr(record, "include_code", False)

        request = IndexRequest(
            folder_path=folder_path,
            include_code=include_code,
            recursive=True,
            force=False,  # Always incremental — ManifestTracker handles the diff
        )
        try:
            result = await self._job_service.enqueue_job(
                request=request,
                operation="index",
                force=False,   # Enable dedupe check — skip if already queued
                source="auto", # Mark as watcher-triggered for BGINC-04
            )
            if result.dedupe_hit:
                logger.debug(
                    f"Auto-reindex skipped (existing job {result.job_id}): "
                    f"{folder_path}"
                )
            else:
                logger.info(
                    f"Auto-reindex queued job_id={result.job_id}: {folder_path}"
                )
        except Exception:
            logger.exception(f"Failed to enqueue auto-reindex for {folder_path}")
```

### FolderRecord Extension

```python
# Source: agent_brain_server/services/folder_manager.py (MODIFY)
@dataclass
class FolderRecord:
    folder_path: str
    chunk_count: int
    last_indexed: str
    chunk_ids: list[str]
    # NEW — backward compatible (v7.0 JSONL missing these fields loads with defaults)
    watch_mode: str = "off"               # "off" | "auto"
    watch_debounce_seconds: int | None = None  # None = use global default
    include_code: bool = False            # Preserve original indexing setting

# In _load_jsonl — use data.get() for all new fields:
record = FolderRecord(
    folder_path=data["folder_path"],
    chunk_count=data["chunk_count"],
    last_indexed=data["last_indexed"],
    chunk_ids=data["chunk_ids"],
    watch_mode=data.get("watch_mode", "off"),
    watch_debounce_seconds=data.get("watch_debounce_seconds", None),
    include_code=data.get("include_code", False),
)
```

### JobRecord source Field

```python
# Source: agent_brain_server/models/job.py (MODIFY JobRecord)
class JobRecord(BaseModel):
    # ... existing fields (unchanged) ...
    source: str = Field(
        default="manual",
        description="Job source: 'manual' (user-triggered) or 'auto' (watcher-triggered)",
    )
```

`JobSummary.from_record()` adds `source` field:

```python
class JobSummary(BaseModel):
    # ... existing fields ...
    source: str = Field(default="manual", description="Job source: manual or auto")

    @classmethod
    def from_record(cls, record: JobRecord) -> "JobSummary":
        return cls(
            # ... existing fields ...
            source=record.source,
        )
```

### enqueue_job() source Parameter

```python
# Source: agent_brain_server/job_queue/job_service.py (MODIFY enqueue_job)
async def enqueue_job(
    self,
    request: IndexRequest,
    operation: str = "index",
    force: bool = False,
    allow_external: bool = False,
    source: str = "manual",  # NEW parameter, default preserves backward compat
) -> JobEnqueueResponse:
    # ... existing logic ...
    job = JobRecord(
        # ... existing fields ...
        source=source,  # NEW
    )
```

### CLI folders add --watch --debounce flags

```python
# Source: agent_brain_cli/commands/folders.py (MODIFY add_folder_cmd)
@folders_group.command("add")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
# ... existing options ...
@click.option(
    "--watch",
    "watch_mode",
    type=click.Choice(["off", "auto"], case_sensitive=False),
    default=None,
    help="Watch mode for auto-reindex: 'auto' enables watching, 'off' disables (default: off)",
)
@click.option(
    "--debounce",
    "debounce_seconds",
    type=int,
    default=None,
    help="Debounce interval in seconds before triggering reindex (default: server global default of 30s)",
)
def add_folder_cmd(
    folder_path: str,
    url: str | None,
    include_code: bool,
    json_output: bool,
    watch_mode: str | None,
    debounce_seconds: int | None,
) -> None:
    # ... pass watch_mode and debounce_seconds to index API call ...
```

The `client.index()` call must pass `watch_mode` and `debounce_seconds` to the server. The server's `IndexRequest` model needs these fields added, and the `/index` router must pass them to `FolderManager.add_folder()` and then to `FileWatcherService.add_folder_watch()`.

### jobs table Source column

```python
# Source: agent_brain_cli/commands/jobs.py (MODIFY _create_jobs_table)
def _create_jobs_table(jobs: list[dict[str, Any]]) -> Table:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Status")
    table.add_column("Source")          # NEW column
    table.add_column("Folder", max_width=40)
    table.add_column("Progress", justify="right")
    table.add_column("Enqueued")
    # ... per-row: source = job.get("source", "manual") ...
    # style: "auto" shown in dim cyan, "manual" shown in default
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `watchdog` + threading bridge | `watchfiles` native `async for` | watchfiles ~2020 | Eliminates all thread-safety complexity; already installed |
| Per-file debounce timers | Per-folder debounce in `awatch(debounce=N)` | Architecture decision for v8.0 | One job per debounce window regardless of file count |
| Separate watcher config store | Extend `FolderRecord` dataclass | Architecture decision for v8.0 | Single source of truth in `indexed_folders.jsonl` |

**Deprecated/outdated (per pre-existing ARCHITECTURE.md):**
- The ARCHITECTURE.md code sample uses `watchdog` with `threading.Timer` — this is the WRONG pattern for this project. The user-confirmed CONTEXT.md says use `watchfiles`. All implementation must use `watchfiles.awatch()`.

---

## Open Questions

1. **`include_code` preservation in FolderRecord**
   - What we know: watcher needs to reconstruct the original `IndexRequest` settings
   - What's unclear: the current `FolderRecord` dataclass does not store `include_code` or other indexing settings
   - Recommendation: Add `include_code: bool = False` to `FolderRecord` dataclass and persist it. The `IndexingService` already calls `folder_manager.add_folder()` after indexing — update that call to pass `include_code`. Alternatively, default to `include_code=True` for watcher jobs (index code unless explicitly excluded). Planner should decide.

2. **`agent-brain folders list` watch_mode display (WATCH-06)**
   - What we know: requirement says "shows watch_mode and watcher status per folder"
   - What's unclear: what "watcher status" means per folder — is it just the config value, or live status (actively watching vs. path missing)?
   - Recommendation: Show watch_mode from `FolderRecord` + whether the `FileWatcherService` has an active task for that folder. The service exposes `self._tasks` keyed by path. Expose `get_watcher_status(folder_path: str) -> str` on `FileWatcherService` returning "watching" or "off".

3. **`/health/status` watcher status (mentioned in CONTEXT.md code_context)**
   - What we know: "Include watcher status (running/stopped, folder count)" mentioned in code_context integration points
   - What's unclear: not in the WATCH-* requirement IDs explicitly, but in CONTEXT.md
   - Recommendation: Add to `/health/status` response: `file_watcher: {running: bool, watched_folders: int}`. Use `app.state.file_watcher_service` in health router. This is low-risk additive work.

4. **`IndexRequest` vs direct `FolderManager.add_folder()` for watch config**
   - What we know: `folders add --watch auto` sets watch config; the current `folders add` routes through the `/index` endpoint via `client.index()`
   - What's unclear: should watch config be part of `IndexRequest` (and stored after index completes) or a separate `PATCH /index/folders/{path}/config` endpoint?
   - Recommendation: Add `watch_mode` and `watch_debounce_seconds` to `IndexRequest` (optional fields with None defaults). The `/index` router passes them through to `FolderManager.add_folder()`. After the indexing job completes, `JobWorker` updates the folder record with the watch config and notifies `FileWatcherService`. This is simpler than a separate config endpoint.

---

## Integration Flow: Folder Add with Watch Mode

This is the key integration path that touches most components:

```
CLI: agent-brain folders add ./src --watch auto --debounce 10
  |
  | POST /index {folder_path: "...", watch_mode: "auto", watch_debounce_seconds: 10}
  v
IndexRequest (add watch_mode, watch_debounce_seconds fields)
  |
  | /index router: enqueue_job(request, source="manual")
  v
JobWorker._process_job()
  |
  | IndexingService runs, completes
  |
  | folder_manager.add_folder(..., watch_mode="auto", watch_debounce_seconds=10)
  v
FolderRecord persisted to indexed_folders.jsonl
  |
  | If watch_mode == "auto":
  |   app.state.file_watcher_service.add_folder_watch(path, debounce_seconds)
  v
asyncio.Task created for folder: runs watchfiles.awatch() loop
```

The watch config must be persisted to `FolderRecord` AFTER indexing succeeds (not before), so a failed index attempt does not register a watcher for a folder with no index.

---

## Sources

### Primary (HIGH confidence)

- `watchfiles` v1.1.1 in project venv — `awatch()` signature, `DefaultFilter` source code, `anyio.Event` stop_event pattern verified by running code
- `anyio.Event()` async context requirement — verified by attempting creation in `__init__()` vs `async def start()`
- Codebase read directly (all referenced files) — `services/folder_manager.py`, `job_queue/job_service.py`, `job_queue/job_worker.py`, `models/job.py`, `models/folders.py`, `api/main.py`, `api/routers/folders.py`, `commands/folders.py`, `commands/jobs.py`
- `poetry show watchfiles` — confirmed v1.1.1 installed as transitive dep via `uvicorn >=0.13`
- `.planning/phases/15-file-watcher-and-background-incremental-updates/15-CONTEXT.md` — all locked decisions
- `.planning/REQUIREMENTS.md` — WATCH-01 through WATCH-07, BGINC-01 through BGINC-04, XCUT-03

### Secondary (MEDIUM confidence)

- `.planning/research/ARCHITECTURE.md` — overall system architecture, service injection patterns
- `.planning/research/SUMMARY.md` — phase rationale and dependency ordering
- `.planning/research/PITFALLS.md` — pitfalls 2, 3, 6, 10 directly applicable to Phase 15

### Tertiary (LOW confidence — validate during implementation)

- `watchfiles` behavior when watched path does not exist (deleted between start and first event) — not tested; add guard in `_start_task()` to check path exists before creating task

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Standard stack (watchfiles) | HIGH | Verified installed and working in project venv; awatch() pattern tested |
| Architecture patterns | HIGH | Per-folder task pattern verified with live code test; mirrors existing _job_worker lifespan pattern |
| FolderRecord extension | HIGH | Current code read; `data.get()` backward compat pattern is established in codebase already |
| JobRecord source field | HIGH | Pydantic `default="manual"` backward compat; existing JSONL loads without source field → default applied |
| CLI changes | HIGH | Existing Click pattern with `--include-code` is the exact model; --watch/--debounce follow same structure |
| anyio.Event in async context | HIGH | Verified by running code in project venv |
| DefaultFilter exclusions | HIGH | Verified by reading DefaultFilter source in project venv |
| Open Questions (include_code, watch status) | MEDIUM | Design choices not locked in CONTEXT.md; recommend but planner should confirm |

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (watchfiles 1.1.1 is pinned as transitive dep; stable API)
