---
name: agent-brain-inject
description: Inject custom metadata into chunks during indexing via Python scripts or JSON metadata files
parameters:
  - name: path
    description: Path to documents to index with injection
    required: true
  - name: script
    description: Path to Python injector script (must export process_chunk function)
    required: false
  - name: folder-metadata
    description: Path to JSON file with static metadata to merge into all chunks
    required: false
  - name: dry-run
    description: Validate injector against sample chunks without indexing
    required: false
    default: false
skills:
  - using-agent-brain
---

# Content Injection

## Purpose

Enrich chunk metadata during indexing using custom Python scripts or static JSON metadata. Injectors run after chunking but before embedding (Step 2.5 in the pipeline), so enriched metadata is stored alongside vectors in the index.

At least one of `--script` or `--folder-metadata` must be provided.

## Usage

```
/agent-brain:agent-brain-inject <path> --script <script.py>
/agent-brain:agent-brain-inject <path> --folder-metadata <metadata.json>
/agent-brain:agent-brain-inject <path> --script <script.py> --folder-metadata <metadata.json>
/agent-brain:agent-brain-inject <path> --script <script.py> --dry-run
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| path | Yes | - | Path to documents to index |
| --script | No* | - | Python script exporting `process_chunk(chunk: dict) -> dict` |
| --folder-metadata | No* | - | JSON file with static key-value metadata |
| --dry-run | No | false | Validate injector against sample chunks without creating a job |
| --chunk-size | No | 512 | Target chunk size in tokens |
| --chunk-overlap | No | 50 | Overlap between chunks in tokens |
| --no-recursive | No | false | Don't scan subdirectories |
| --include-code | No | false | Include code files in indexing |
| --include-type | No | - | File type presets (e.g., python,docs) |
| --languages | No | - | Comma-separated language list for code |
| --code-strategy | No | ast_aware | Code splitting: ast_aware or text_based |
| --include-patterns | No | - | Additional glob include patterns |
| --exclude-patterns | No | - | Additional glob exclude patterns |
| --generate-summaries | No | false | Generate LLM summaries for better search |
| --force | No | false | Force re-indexing (bypass manifest) |
| --allow-external | No | false | Allow paths outside project directory |
| --json | No | false | Output results as JSON |

*At least one of `--script` or `--folder-metadata` is required.

### Examples

```
# Add project tags via script
/agent-brain:agent-brain-inject ./docs --script enrich.py

# Merge static metadata from JSON
/agent-brain:agent-brain-inject ./src --folder-metadata project-meta.json --include-code

# Combine script + static metadata
/agent-brain:agent-brain-inject ./docs --script classify.py --folder-metadata team-meta.json

# Validate before indexing
/agent-brain:agent-brain-inject ./docs --script enrich.py --dry-run

# With file type presets
/agent-brain:agent-brain-inject ./src --script enrich.py --include-type python,docs
```

## Execution

Run the inject command with appropriate options:

**Script injection:**
```bash
agent-brain inject <path> --script <script.py>
```

**Folder metadata injection:**
```bash
agent-brain inject <path> --folder-metadata <metadata.json>
```

**Dry-run validation:**
```bash
agent-brain inject <path> --script <script.py> --dry-run
```

### Expected Output

**Normal injection:**
```
Inject job queued!

Job ID: abc123
Folder: /home/user/docs
Script: /home/user/enrich.py
Status: queued

Use 'agent-brain jobs' to monitor progress.
```

**Dry-run:**
```
Dry-run validation complete

Sampled: 3 files, 10 chunks
Script: /home/user/enrich.py
Keys added: ["project", "team", "category"]
Errors: 0

Ready to run without --dry-run.
```

## Injector Script Protocol

Scripts must export a `process_chunk` function:

```python
def process_chunk(chunk: dict) -> dict:
    """Enrich a single chunk with custom metadata."""
    chunk["project"] = "my-project"
    chunk["team"] = "backend"
    return chunk
```

**Input keys available:** `chunk_id`, `content`, `source`, `language`, `start_line`, `end_line`, `summary`

**Constraints:**
- Values must be scalars (str, int, float, bool) — lists and dicts are stripped for ChromaDB compatibility
- Keys in the core schema (`chunk_id`, `source`, etc.) cannot be overwritten
- Exceptions are caught per-chunk and logged as warnings (pipeline continues)
- Scripts should be pure functions with no side effects

See `docs/INJECTOR_PROTOCOL.md` for the full protocol specification with examples.

## Folder Metadata JSON Format

```json
{
  "project": "my-project",
  "team": "backend",
  "version": "2.0"
}
```

All key-value pairs are merged into every chunk from the folder. Same scalar value constraint applies.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| No injection option | Neither --script nor --folder-metadata provided | Provide at least one |
| Script not found | Invalid path to .py file | Verify script path exists |
| Metadata file not found | Invalid path to .json file | Verify JSON file path exists |
| Script missing process_chunk | Script doesn't export required function | Add `def process_chunk(chunk: dict) -> dict` |
| Server not running | Agent Brain server is stopped | Run `agent-brain start` first |
| Non-scalar value stripped | List or dict in metadata | Use only str, int, float, bool values |

### Recovery Commands

```bash
# Validate script first
agent-brain inject ./docs --script enrich.py --dry-run

# Check server status
agent-brain status

# Monitor job progress
agent-brain jobs --watch
```

## Notes

- Inject is a superset of index — all index options are available
- Injection happens at Step 2.5 in the pipeline (after chunking, before embedding)
- Per-chunk errors don't crash the pipeline — they're logged as warnings
- Paths are resolved to absolute before sending to the server
- Use `--dry-run` to validate scripts before committing to a full indexing run
