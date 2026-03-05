# Injector Protocol

Content injection enriches chunk metadata during indexing with custom data via Python
scripts or static JSON files. This enables tagging, classification, and project-specific
metadata to be stored alongside each document chunk in ChromaDB.

## Quick Start

```bash
# Using a Python script
agent-brain inject --script enrich.py /path/to/docs

# Using folder metadata JSON
agent-brain inject --folder-metadata metadata.json /path/to/docs

# Both combined
agent-brain inject --script enrich.py --folder-metadata metadata.json /path/to/docs

# Validate before indexing
agent-brain inject --dry-run --script enrich.py /path/to/docs
```

## The `process_chunk` Protocol

An injector script must export a top-level function named `process_chunk`:

```python
def process_chunk(chunk: dict) -> dict:
    ...
```

### Input

The `chunk` argument is a flat `dict` produced by `ChunkMetadata.to_dict()`. It
includes the following keys:

| Key | Type | Description |
|-----|------|-------------|
| `chunk_id` | `str` | Unique identifier for the chunk |
| `source` | `str` | Absolute path to the source file |
| `file_name` | `str` | Base file name |
| `chunk_index` | `int` | Position within the file |
| `total_chunks` | `int` | Total chunks from the file |
| `source_type` | `str` | `doc`, `code`, or `test` |
| `created_at` | `str` | ISO 8601 timestamp |
| `language` | `str \| None` | Programming language (code chunks) |
| `heading_path` | `str \| None` | Markdown heading hierarchy |
| `section_title` | `str \| None` | Nearest heading |
| `content_type` | `str \| None` | `function`, `class`, `module`, etc. |
| `symbol_name` | `str \| None` | Name of the code symbol |
| `symbol_kind` | `str \| None` | Kind of symbol |
| `start_line` | `int \| None` | Start line in source file |
| `end_line` | `int \| None` | End line in source file |
| `section_summary` | `str \| None` | LLM summary of section |
| `prev_section_summary` | `str \| None` | Summary of previous section |
| `docstring` | `str \| None` | Extracted docstring |
| `parameters` | `str \| None` | Function parameters |
| `return_type` | `str \| None` | Function return type |
| `decorators` | `str \| None` | Applied decorators |
| `imports` | `str \| None` | Relevant imports |

Plus any `extra` keys already present from earlier injection steps.

### Output

Return a `dict` with the enriched metadata. New keys are stored in
`ChunkMetadata.extra`. **Existing fixed keys** (`chunk_id`, `source`, `file_name`,
etc.) cannot be overridden — only new keys from the returned dict are captured.

### Value Constraints

All values in the returned dict must be **scalars**: `str`, `int`, `float`, or `bool`.
Lists and dicts are stripped with a warning. This is a ChromaDB constraint — metadata
values must be flat.

### Exception Handling

Per-chunk exceptions are caught, logged as warnings, and the original chunk is
preserved. The indexing job continues. A failure in `process_chunk` for one chunk
never crashes the job.

## Example Scripts

### `enrich.py` — Add project tags and conditional enrichment

```python
def process_chunk(chunk: dict) -> dict:
    enriched = {}

    # Static project tag applied to all chunks
    enriched["project"] = "my-project"
    enriched["team"] = "platform"

    # Conditional enrichment based on source type
    source_type = chunk.get("source_type", "")
    if source_type == "code":
        enriched["review_required"] = True
        language = chunk.get("language") or "unknown"
        enriched["code_language"] = language.lower()
    elif source_type == "doc":
        enriched["searchable"] = True

    # Enrich based on file path
    source = chunk.get("source", "")
    if "deprecated" in source:
        enriched["deprecated"] = True

    return enriched
```

### `classify.py` — Classify chunks by content

```python
import os

CATEGORY_MAP = {
    ".py": "python-source",
    ".ts": "typescript-source",
    ".tsx": "react-component",
    ".md": "documentation",
    ".rst": "documentation",
    ".yaml": "configuration",
    ".yml": "configuration",
    ".json": "configuration",
    ".toml": "configuration",
}

def process_chunk(chunk: dict) -> dict:
    source = chunk.get("source", "")
    ext = os.path.splitext(source)[1].lower()
    category = CATEGORY_MAP.get(ext, "other")
    return {"doc_category": category}
```

## Folder Metadata JSON

A folder metadata file applies the same static key/value pairs to every chunk from the
indexed folder. It must be a JSON object at the root level with scalar values only.

### Example

```json
{
    "project": "my-project",
    "version": "2.1.0",
    "team": "platform",
    "environment": "production",
    "indexed_by": "ci-pipeline"
}
```

The keys from this file are merged into each chunk **before** the injector script runs,
so the script can read and build on them.

## Dry-Run Mode

`--dry-run` validates injection without creating a job or modifying the index.

**What it does:**

1. Loads up to 3 sample files from the target folder.
2. Chunks them using the configured chunking settings.
3. Applies the injector script and/or folder metadata to the sample chunks.
4. Returns a report with chunk count and a sample of injected keys.
5. Does NOT enqueue a job or write to ChromaDB.

**Example output:**

```
Dry-run validation complete.

Folder: /path/to/docs
Report: Validated 10 chunks across 3 files. Injected keys: project, team, doc_category
Status: completed
```

Use dry-run before production indexing to verify scripts produce the expected output.

## Best Practices

- Keep `process_chunk` **pure**: avoid side effects, file writes, or network calls.
- Avoid top-level code that runs on import (expensive operations, network requests).
- Use `--dry-run` to verify your script before indexing large corpora.
- Use folder metadata for **static project-wide tags** (project name, team, version).
- Use scripts for **conditional or computed enrichment** based on chunk content.
- Return `{}` from `process_chunk` if no enrichment is needed for a given chunk.
- Keep script import chains shallow — the script runs in the server process.

## Limitations

- Scripts run **in the server process** (same machine, same Python interpreter).
- There is **no sandboxing** — scripts have full Python access to the filesystem and
  network.
- Values must be **flat scalars** (`str`, `int`, `float`, `bool`). Nested dicts and
  lists are stripped.
- The script path must be **accessible from the server process**. Paths are resolved by
  the CLI and sent as absolute paths; the server must be able to read the file at that
  path.
- Overriding core schema fields (`chunk_id`, `source`, `file_name`, etc.) is silently
  ignored — only new keys are captured.
