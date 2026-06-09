"""SIGTERM-ignoring stub child for Plan 60-02's SIGKILL escalation test.

Run as a subprocess; ignores SIGTERM via signal.signal(SIGTERM, SIG_IGN)
then sleeps for ``--sleep`` seconds (default 30). SIGKILL still terminates
the process unconditionally — that is exactly what Plan 60-02's close()
escalation relies on.

Portable: no shell scripts, runs on macOS/Linux. Windows is NOT supported
in Phase 60 per CONTEXT.md deferred ideas.

Invoked from tests via:

    subprocess.Popen([sys.executable, str(stub_path), "--sleep", "10"])
"""

from __future__ import annotations

import argparse
import signal
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", type=float, default=30.0)
    args = parser.parse_args()

    # Trap SIGTERM and intentionally ignore it. The Plan 60-02 close()
    # escalation MUST detect that the process is still alive after the
    # grace period and SIGKILL it.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    # Print a ready marker so tests can synchronize on stdout.
    print("READY", flush=True)

    time.sleep(args.sleep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
