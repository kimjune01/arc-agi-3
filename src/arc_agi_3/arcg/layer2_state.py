"""Layer 2 — state & determinism. Exploits "a state IS its action sequence".

`snapshot` names the current sequence; `peek` reads any cached state for free (no
API, no budget); `restore` re-occupies a state the only way the server allows —
full RESET + replay — which costs budget but, as a free side effect, measures
whether the replay reproduced the cached frame (the determinism property, which
the rulebook does NOT guarantee).

What to DO on a determinism mismatch is deferred policy; `restore` only reports
the verdict.
"""

from __future__ import annotations

import numpy as np

from ..perception import render_grid
from . import layer0_protocol, layer1_intent, store


def history() -> str:
    sess = store.load()
    snaps = store.list_snapshots()
    lines = [
        f"game {sess.game_id} | {len(sess.history)} actions since RESET | "
        f"budget {sess.actions_spent}" + (f"/{sess.budget_cap}" if sess.budget_cap else "")
        + f" | resets {sess.resets}",
        "sequence: " + (" ".join(sess.history) if sess.history else "(empty)"),
    ]
    if snaps:
        lines.append("snapshots: " + ", ".join(snaps))
    return "\n".join(lines)


def snapshot(label: str) -> str:
    sess = store.load()
    store.save_snapshot(label, sess.game_id, sess.history)
    return f"snapshot {label!r} = [{' '.join(sess.history)}] ({len(sess.history)} actions)"


def peek(label: str) -> str:
    """Cache-only view of a snapshot's state. No API, no budget spent."""
    snap = store.load_snapshot(label)
    frame = store.cache_get(snap["game_id"], snap["sequence"])
    if frame is None:
        return f"{label!r} not in cache (never reached live). Use `restore` to visit it."
    grid = np.asarray(frame["grid"], np.int16)
    return (f"peek {label!r} (cache, free) | state {frame['state']} | "
            f"score {frame['score']}/{frame.get('win_score')} | "
            f"{len(snap['sequence'])} actions\n"
            f"grid (64x64 hex, '.'=empty):\n{render_grid(grid)}")


def _replay(token: str) -> None:
    if ":" in token:  # ACTION6:x,y
        name, coords = token.split(":", 1)
        x, y = (int(v) for v in coords.split(","))
        layer0_protocol.act(name, x=x, y=y, reasoning="replay")
    else:
        layer0_protocol.act(token, reasoning="replay")


def restore(label: str) -> str:
    """RESET + replay to a snapshot. Costs budget; verifies determinism for free."""
    snap = store.load_snapshot(label)
    sequence = snap["sequence"]
    expected = store.cache_get(snap["game_id"], sequence)  # capture BEFORE replay

    layer0_protocol.reset(full=True)
    spent_before = store.load().actions_spent
    for token in sequence:
        _replay(token)
    sess = store.load()
    spent = sess.actions_spent - spent_before + 1  # +1 for the RESET-then-replay anchor

    # determinism verdict (free: we replayed anyway)
    if expected is None:
        verdict = "no cached reference (cached now); determinism unmeasured"
    elif expected["grid"] == sess.grid:
        verdict = "DETERMINISTIC ✓ (replay reproduced the cached frame)"
    else:
        a, b = np.asarray(expected["grid"]), np.asarray(sess.grid)
        n = int((a != b).sum()) if a.shape == b.shape else -1
        verdict = (f"NON-DETERMINISTIC ✗ ({n} cells differ from cache) — "
                   f"FINDING: post-RESET replay is not reproducible")

    return (f"restored {label!r}: replayed {len(sequence)} actions "
            f"(~{spent} budget spent)\n{verdict}\n{layer1_intent.look(no_grid=True)}")
