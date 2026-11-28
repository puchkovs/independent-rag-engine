"""The memory rules of the evaluation scripts that load a model, in one place.

This machine is small and shared. A script that loads a model refuses to start unless the kernel
reports enough memory available for the model plus the 1 GiB of headroom used everywhere else, and
a watchdog stops it if free memory falls dangerously low while it runs. Nothing here frees memory
or touches another process: a refusal is a result, reported with exit code 3.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

GIB = 1024**3
HEADROOM_GIB = 1.0
STOP_BELOW_GIB = 0.45


def available() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return 0


def require(model_gib: float, *, what: str) -> None:
    """Exit with code 3 and a report unless ``model_gib`` plus the headroom is available."""
    needed = model_gib + HEADROOM_GIB
    if available() < needed * GIB:
        print(
            json.dumps(
                {
                    "result": "refused_by_resource_gate",
                    "what": what,
                    "available_gib": round(available() / GIB, 2),
                    "needed_gib": round(needed, 2),
                }
            )
        )
        sys.exit(3)


def watchdog() -> None:
    """Stop this process if free memory falls under ``STOP_BELOW_GIB`` (checked twice a second)."""

    def watch() -> None:
        while True:
            if available() < STOP_BELOW_GIB * GIB:
                sys.stderr.write("memory watchdog: free memory is too low, stopping\n")
                os._exit(7)
            time.sleep(0.5)

    threading.Thread(target=watch, daemon=True).start()
