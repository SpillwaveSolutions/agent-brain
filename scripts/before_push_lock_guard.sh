#!/usr/bin/env bash
# Wrap-around guard for `task before-push` — see issue #174.
#
# Problem: in-monorepo `poetry install` (run transitively by before-push)
# can silently rewrite agent-brain-cli/poetry.lock to point at the local
# ../agent-brain-server build instead of the PyPI version pinned in
# pyproject.toml. If that lockfile change gets committed, CI breaks
# because CI fetches agent-brain-rag from PyPI.
#
# Solution: snapshot which lockfiles were git-clean at task entry. On
# task exit (via Taskfile defer), revert any clean-at-entry lockfile
# that's now dirty. Files that were ALREADY dirty at entry are left
# alone — preserves intentional lockfile edits during dev.

set -euo pipefail

SNAPSHOT_FILE="${TMPDIR:-/tmp}/.ab-before-push-lock-snapshot"
LOCK_FILES=(
    "agent-brain-server/poetry.lock"
    "agent-brain-cli/poetry.lock"
)

case "${1:-}" in
    start)
        : > "$SNAPSHOT_FILE"
        for f in "${LOCK_FILES[@]}"; do
            if [ ! -f "$f" ]; then
                continue
            fi
            if git diff --quiet -- "$f" 2>/dev/null; then
                printf '%s\n' "$f" >> "$SNAPSHOT_FILE"
            fi
        done
        ;;
    check)
        if [ ! -f "$SNAPSHOT_FILE" ]; then
            exit 0
        fi
        reverted=0
        while IFS= read -r f; do
            if [ -z "$f" ]; then
                continue
            fi
            if ! git diff --quiet -- "$f" 2>/dev/null; then
                printf 'WARN: %s drifted during before-push (likely monorepo bootstrap).\n' "$f" >&2
                printf '      Reverting to HEAD. If you intentionally changed it, commit it first then re-run.\n' >&2
                git checkout HEAD -- "$f"
                reverted=1
            fi
        done < "$SNAPSHOT_FILE"
        rm -f "$SNAPSHOT_FILE"
        if [ "$reverted" = "1" ]; then
            printf '      (lock-drift guard #174 — see https://github.com/SpillwaveSolutions/agent-brain/issues/174)\n' >&2
        fi
        ;;
    *)
        printf 'Usage: %s {start|check}\n' "$0" >&2
        exit 2
        ;;
esac
