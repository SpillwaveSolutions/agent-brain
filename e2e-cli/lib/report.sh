#!/usr/bin/env bash
set -euo pipefail

REPORT_JSON="${RUNS_DIR}/report.json"
REPORT_MD="${RUNS_DIR}/report.md"
REPORT_TSV="${RUNS_DIR}/report.tsv"

report_init() {
  mkdir -p "$RUNS_DIR"
  : > "$REPORT_TSV"
  cat > "$REPORT_MD" <<EOF
# E2E Run Report

- Run ID: ${RUN_ID}
- Adapter: ${ADAPTER_NAME}
- Results root: ${RUNS_DIR}

| Scenario | Status | Duration (s) | Assertions | Message |
|---|---|---:|---:|---|
EOF
  printf '{\n  "run_id": "%s",\n  "adapter": "%s",\n  "results_root": "%s",\n  "results": []\n}\n' \
    "$RUN_ID" "$ADAPTER_NAME" "$RUNS_DIR" > "$REPORT_JSON"
}

report_add_result() {
  local scenario="$1"
  local status="$2"
  local duration="$3"
  local assertions_passed="$4"
  local assertions_total="$5"
  local message="$6"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$scenario" "$status" "$duration" "$assertions_passed" "$assertions_total" "$message" >> "$REPORT_TSV"
  printf '| %s | %s | %s | %s/%s | %s |\n' \
    "$scenario" "$status" "$duration" "$assertions_passed" "$assertions_total" "${message:-}" >> "$REPORT_MD"
}

report_finalize() {
  python3 - "$REPORT_TSV" "$REPORT_JSON" "$RUN_ID" "$ADAPTER_NAME" "$RUNS_DIR" <<'PY'
import json
import sys
from pathlib import Path

tsv_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
run_id, adapter, runs_dir = sys.argv[3:6]
results = []
if tsv_path.exists():
    for line in tsv_path.read_text().splitlines():
        if not line:
            continue
        scenario, status, duration, passed, total, message = line.split("\t", 5)
        results.append(
            {
                "scenario": scenario,
                "status": status,
                "duration_sec": duration,
                "assertions_passed": passed,
                "assertions_total": total,
                "message": message,
            }
        )
payload = {
    "run_id": run_id,
    "adapter": adapter,
    "results_root": runs_dir,
    "results": results,
}
json_path.write_text(json.dumps(payload, indent=2) + "\n")
PY
}

report_all() {
  report_finalize
}
