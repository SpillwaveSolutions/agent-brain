# Quickstart: Multi-Instance Architecture

## Per-Project Mode (Default)

### 1. Initialize a project

```bash
cd /path/to/my-repo
doc-serve init
# Creates .claude/doc-serve/config.json with defaults
```

### 2. Start the server

```bash
doc-serve start
# → Server started at http://127.0.0.1:49321
# → State directory: /path/to/my-repo/.claude/doc-serve/
# → Discovery file: /path/to/my-repo/.claude/doc-serve/runtime.json
```

### 3. Check status (from any subdirectory)

```bash
cd /path/to/my-repo/src/deep/nested
doc-serve status
# → Doc-serve running at http://127.0.0.1:49321 (project mode)
# → Indexed: 1,234 chunks from 56 files
```

### 4. Index documents

```bash
doc-serve index /path/to/my-repo/docs
```

### 5. Query

```bash
doc-serve query "how does authentication work?"
```

### 6. Stop

```bash
doc-serve stop
# → Server stopped. Cleanup complete.
```

## Multiple Projects

```bash
# Terminal 1
cd /path/to/project-a
doc-serve start
# → Started on port 49321

# Terminal 2
cd /path/to/project-b
doc-serve start
# → Started on port 49322 (auto-assigned, no conflict)

# List all running instances
doc-serve list
# → project-a: http://127.0.0.1:49321 (project mode)
# → project-b: http://127.0.0.1:49322 (project mode)
```

## Shared Daemon Mode (Optional)

```bash
# Start shared daemon
doc-serve start --mode shared
# → Shared daemon started at http://127.0.0.1:45123

# From project A
cd /path/to/project-a
doc-serve init --mode shared
doc-serve start
# → Registered with shared daemon at http://127.0.0.1:45123

# From project B
cd /path/to/project-b
doc-serve init --mode shared
doc-serve start
# → Registered with shared daemon at http://127.0.0.1:45123
```

## For Skill Authors

```python
from doc_serve_client import discover_or_start

# Discovers running instance or starts one
runtime = discover_or_start(project_root=Path.cwd())
base_url = runtime.base_url  # e.g., "http://127.0.0.1:49321"
```

## Verification Checklist

- [ ] `doc-serve init` creates `.claude/doc-serve/config.json`
- [ ] `doc-serve start` creates `runtime.json` with actual port
- [ ] `doc-serve status` works from any subdirectory
- [ ] `doc-serve stop` removes all runtime artifacts
- [ ] Two projects can run concurrently on different ports
- [ ] Crashed instance recovers on next `doc-serve start`
- [ ] `.claude/doc-serve/runtime.json` is in `.gitignore`
