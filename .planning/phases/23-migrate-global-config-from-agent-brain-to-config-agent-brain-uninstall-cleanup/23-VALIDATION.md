---
phase: 23
slug: migrate-global-config-from-agent-brain-to-config-agent-brain-uninstall-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `agent-brain-cli/pyproject.toml` (pytest section) |
| **Quick run command** | `cd agent-brain-cli && poetry run pytest tests/test_xdg_paths.py tests/test_config.py -x` |
| **Full suite command** | `cd agent-brain-cli && poetry run pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd agent-brain-cli && poetry run pytest tests/test_xdg_paths.py tests/test_config.py tests/test_uninstall_command.py tests/test_multi_instance_commands.py -x`
- **After every plan wave:** Run `cd agent-brain-cli && poetry run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | XDG-01 | unit | `pytest tests/test_xdg_paths.py::TestXdgPaths::test_config_dir_default -x` | ❌ W0 | ⬜ pending |
| 23-01-02 | 01 | 1 | XDG-02 | unit | `pytest tests/test_xdg_paths.py::TestXdgPaths::test_state_dir_default -x` | ❌ W0 | ⬜ pending |
| 23-01-03 | 01 | 1 | XDG-03 | unit | `pytest tests/test_xdg_paths.py::TestXdgPaths::test_config_dir_env_var -x` | ❌ W0 | ⬜ pending |
| 23-01-04 | 01 | 1 | MIG-01 | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_copies_and_removes -x` | ❌ W0 | ⬜ pending |
| 23-01-05 | 01 | 1 | MIG-01 | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_skips_if_xdg_exists -x` | ❌ W0 | ⬜ pending |
| 23-01-06 | 01 | 1 | MIG-02 | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_notice_to_stderr -x` | ❌ W0 | ⬜ pending |
| 23-01-07 | 01 | 1 | MIG-02 | unit | `pytest tests/test_xdg_paths.py::TestMigration::test_migration_failure_nonfatal -x` | ❌ W0 | ⬜ pending |
| 23-02-01 | 02 | 2 | CFG-01 | unit | `pytest tests/test_config.py::TestFindConfigFile::test_xdg_before_legacy -x` | ❌ W0 | ⬜ pending |
| 23-02-02 | 02 | 2 | MIG-03 | unit | `pytest tests/test_config.py::TestFindConfigFile::test_legacy_fallback_prints_deprecation -x` | ❌ W0 | ⬜ pending |
| 23-02-03 | 02 | 2 | REG-01 | unit | `pytest tests/test_multi_instance_commands.py -k test_registry_uses_xdg -x` | ❌ W0 | ⬜ pending |
| 23-02-04 | 02 | 2 | REG-02 | unit | `pytest tests/test_multi_instance_commands.py -k test_remove_registry_uses_xdg -x` | ❌ W0 | ⬜ pending |
| 23-03-01 | 03 | 3 | UNI-01 | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_removes_global_dirs -x` | ❌ W0 | ⬜ pending |
| 23-03-02 | 03 | 3 | UNI-01 | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_stops_servers_first -x` | ❌ W0 | ⬜ pending |
| 23-03-03 | 03 | 3 | UNI-02 | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_confirmation_prompt -x` | ❌ W0 | ⬜ pending |
| 23-03-04 | 03 | 3 | UNI-03 | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_yes_flag_skips_prompt -x` | ❌ W0 | ⬜ pending |
| 23-03-05 | 03 | 3 | UNI-01 | unit | `pytest tests/test_uninstall_command.py::TestUninstallCommand::test_does_not_touch_project_dirs -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_xdg_paths.py` — stubs for XDG-01 through MIG-03 (new module tests)
- [ ] `tests/test_uninstall_command.py` — stubs for UNI-01 through UNI-03
- [ ] `agent_brain_cli/xdg_paths.py` — the shared helper module itself must be created

*Existing infrastructure covers test framework and conftest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Migration notice visible to user | MIG-02 | stderr output in real terminal | Run `agent-brain start` with `~/.agent-brain/` present, confirm notice appears |
| Deprecation warning visible | MIG-03 | Real config file at legacy path | Place config.yaml at `~/.agent-brain/`, run `agent-brain status`, confirm warning |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
