---
created: 2026-02-20T19:24:12.153Z
title: Add docx2txt dependency or graceful skip for docx files
area: api
severity: low
files:
  - agent-brain-server/agent_brain_server/indexing/document_loader.py:242
  - agent-brain-server/pyproject.toml
---

## Problem

Indexing jobs fail with `docx2txt is required to read .docx files` when the target folder contains Word documents. `document_loader.py:242` lists `.docx` in `DOCUMENT_EXTENSIONS` but `docx2txt` is not a package dependency.

Workaround used: `uv tool install agent-brain-cli==6.0.1 --with asyncpg --with docx2txt`

## Solution

Either:

**Option A (preferred):** Add `docx2txt` as a required dependency in `agent-brain-server/pyproject.toml`. It's a small package and `.docx` is a commonly encountered file type.

**Option B:** Gracefully skip `.docx` files with a warning when `docx2txt` is not installed:
```python
if ext == '.docx':
    try:
        import docx2txt
    except ImportError:
        logger.warning(f"Skipping {file_path}: docx2txt not installed (pip install docx2txt)")
        continue
```

Option B is safer if we want to keep the package lightweight. The key improvement is not crashing the entire indexing job.
