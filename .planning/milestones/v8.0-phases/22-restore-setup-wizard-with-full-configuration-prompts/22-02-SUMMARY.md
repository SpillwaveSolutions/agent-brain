---
phase: 22-restore-setup-wizard-with-full-configuration-prompts
plan: "02"
subsystem: agent-brain-server/tests
tags:
  - regression-tests
  - setup-wizard
  - plugin-commands
  - test-coverage
dependency_graph:
  requires:
    - 22-01 (wizard content must exist before regression tests can pass)
  provides:
    - Regression prevention tests for wizard content in plugin command files
  affects:
    - agent-brain-server/tests/test_plugin_wizard_spec.py
tech_stack:
  added: []
  patterns:
    - pytest file-content assertions
    - Path(__file__).parents[N] for cross-package file location
    - autouse fixture for graceful CI degradation
key_files:
  created:
    - agent-brain-server/tests/test_plugin_wizard_spec.py
  modified: []
decisions:
  - autouse fixture skips all tests if plugin dir not found — graceful degradation for CI
  - 11 tests instead of planned 10 — added test_setup_wizard_writes_config_yaml for completeness
  - Descriptive assertion messages identify exact wizard step to restore on failure
metrics:
  duration: "~5 min"
  completed_date: "2026-03-12"
  tasks_completed: 1
  files_created: 1
---

# Phase 22 Plan 02: Wizard Regression Tests — Summary

**One-liner**: 11 pytest tests in `test_plugin_wizard_spec.py` assert all required wizard sections remain in plugin command markdown files — any future removal of a wizard step causes immediate test failure.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create regression test for wizard content | 95dd3cb | agent-brain-server/tests/test_plugin_wizard_spec.py |

## What Was Built

### test_plugin_wizard_spec.py (11 tests, all passing)

Regression prevention tests that read plugin command markdown files and assert required wizard sections are present:

**agent-brain-setup.md assertions (7 tests):**
- `test_setup_wizard_asks_embedding_provider` — "embedding" + AskUserQuestion present
- `test_setup_wizard_asks_summarization_provider` — "summarization" present (case-insensitive)
- `test_setup_wizard_asks_storage_backend` — "ChromaDB" AND "PostgreSQL" both present
- `test_setup_wizard_asks_graphrag` — "GraphRAG" or "graphrag" present (case-insensitive)
- `test_setup_wizard_asks_query_mode` — "query mode" present (case-insensitive)
- `test_setup_wizard_has_multiple_ask_blocks` — >= 5 AskUserQuestion blocks
- `test_setup_wizard_writes_config_yaml` — "config.yaml" write step present

**agent-brain-config.md assertions (4 tests):**
- `test_config_wizard_has_provider_selection` — AskUserQuestion present
- `test_config_wizard_mentions_chromadb` — "ChromaDB" present
- `test_config_wizard_mentions_postgresql` — "PostgreSQL" present
- `test_config_wizard_mentions_ollama` — "Ollama" present

**Safety fixture:**
- `require_plugin_dir` autouse fixture skips all tests if `agent-brain-plugin/` not found
- Graceful degradation for CI environments that check out only `agent-brain-server/`

**File location:**
Uses `Path(__file__).parents[2] / "agent-brain-plugin"` — test at `agent-brain-server/tests/`, plugin is two parents up.

## Test Results

```
tests/test_plugin_wizard_spec.py::test_setup_wizard_asks_embedding_provider PASSED
tests/test_plugin_wizard_spec.py::test_setup_wizard_asks_summarization_provider PASSED
tests/test_plugin_wizard_spec.py::test_setup_wizard_asks_storage_backend PASSED
tests/test_plugin_wizard_spec.py::test_setup_wizard_asks_graphrag PASSED
tests/test_plugin_wizard_spec.py::test_setup_wizard_asks_query_mode PASSED
tests/test_plugin_wizard_spec.py::test_setup_wizard_has_multiple_ask_blocks PASSED
tests/test_plugin_wizard_spec.py::test_setup_wizard_writes_config_yaml PASSED
tests/test_plugin_wizard_spec.py::test_config_wizard_has_provider_selection PASSED
tests/test_plugin_wizard_spec.py::test_config_wizard_mentions_chromadb PASSED
tests/test_plugin_wizard_spec.py::test_config_wizard_mentions_postgresql PASSED
tests/test_plugin_wizard_spec.py::test_config_wizard_mentions_ollama PASSED

11 passed, 1 warning in 5.36s
```

## Decisions Made

1. 11 tests instead of planned 10 — added `test_setup_wizard_writes_config_yaml` to cover the config write step (important regression risk)
2. `autouse=True` fixture — all tests skip automatically without boilerplate `if not PLUGIN_ROOT.exists()` in each test
3. Descriptive assertion messages name the exact wizard step and step number to restore

## Deviations from Plan

**[Rule 2 - Enhancement]** Added 11th test `test_setup_wizard_writes_config_yaml`
- **Found during:** Task 1 implementation
- **Issue:** Plan specified 10 tests but config.yaml write step (Step 7) is a critical wizard requirement with high regression risk
- **Fix:** Added one additional test covering config.yaml presence
- **Files modified:** agent-brain-server/tests/test_plugin_wizard_spec.py
