"""Append-only operational trace — one JSON line per CLI invocation, for POST-OP
inspection (forensics, budget accounting, backstep / poka-yoke audits, determinism
diffs).

The opposite integrity class from jotter: this is observability, not memory.
Append-only and *duplicate-preserving* (the one log where idempotence is WRONG — you
want every repeat, retry, and guard-bounce, with timing, in order); a free monoid
(concatenation), not the idempotent cache join; human-read after the run, never
reasoned over in-loop. jotter records the *result*; the trace records the *operation*.
"""

from __future__ import annotations

import json
import time

from ..session import STATE_DIR

TRACE_FILE = STATE_DIR / "trace.jsonl"


def emit(event: dict) -> None:
    """Append one event (stamped with `ts`) as a JSON line. Never rewrites history."""
    record = {"ts": round(time.time(), 3), **event}
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")
