"""Phase 60 (MCPHYG-02) stress tests — opt-in only.

Run via ``task mcp:stress:orphan-test`` (slow; NOT in task before-push).

All tests in this package MUST carry the ``pytest.mark.stress`` marker
so the default ``addopts`` filter excludes them.
"""
