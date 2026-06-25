"""Layer 1 — agent action intent + perception.

The agent operates here, in game terms, never in ACTION-numbers. Intent verbs
(`move/interact/click/undo`) translate to Layer 0 raw actions and return the
resulting perception (delta + frame). Perception verbs (`look/diff`) render the
stored frame without acting.

The intent->action mapping is the documented DEFAULT; the real effect "depends on
the title", so it's a hypothesis the agent verifies via deltas. Layer 0 `act
ACTIONn` stays as the escape hatch when the convention doesn't fit a game.
"""

from __future__ import annotations

import numpy as np

from ..perception import describe_objects, diff_grids, find_objects, render_grid
from ..session import Session
from . import layer0_protocol, store

INTENT = {"up": "ACTION1", "down": "ACTION2", "left": "ACTION3", "right": "ACTION4"}


def _observe(sess: Session, *, include_grid: bool = True) -> str:
    cur = np.asarray(sess.grid, dtype=np.int16) if sess.grid else np.zeros((0, 0), np.int16)
    values, counts = np.unique(cur, return_counts=True) if cur.size else ([], [])
    palette = ", ".join(f"{int(v)}:{int(n)}" for v, n in zip(values, counts))
    target = sess.win_score if sess.win_score is not None else "?"
    parts = [
        f"state {sess.state} | score {sess.score}/{target} | "
        f"actions spent {sess.actions_spent}"
        + (f"/{sess.budget_cap}" if sess.budget_cap else ""),
        f"colours (value:count): {palette}",
    ]
    if sess.prev_grid and len(sess.prev_grid) == len(sess.grid):
        delta = diff_grids(np.asarray(sess.prev_grid, np.int16), cur)
        parts.append(f"since last action: {delta.describe()}")
    if include_grid:
        parts.append("grid (64x64 hex, '.'=empty):")
        parts.append(render_grid(cur))
    return "\n".join(parts)


# --- intent (act, then perceive) -----------------------------------------
def move(direction: str) -> str:
    if direction not in INTENT:
        raise SystemExit(f"direction must be one of {list(INTENT)}")
    layer0_protocol.act(INTENT[direction], reasoning=f"move {direction}")
    return _observe(store.load())


def interact() -> str:
    layer0_protocol.act("ACTION5", reasoning="interact")
    return _observe(store.load())


def click(x: int, y: int) -> str:
    layer0_protocol.act("ACTION6", x=x, y=y, reasoning=f"click {x},{y}")
    return _observe(store.load())


def undo() -> str:
    layer0_protocol.act("ACTION7", reasoning="undo")
    return _observe(store.load())


# --- perception (no action) ----------------------------------------------
def look(*, no_grid: bool = False) -> str:
    return _observe(store.load(), include_grid=not no_grid)


def diff() -> str:
    sess = store.load()
    if not (sess.prev_grid and len(sess.prev_grid) == len(sess.grid)):
        return "no prior frame to diff against."
    d = diff_grids(np.asarray(sess.prev_grid, np.int16), np.asarray(sess.grid, np.int16))
    return d.describe(max_cells=40)


def objects(*, with_bg: bool = False, connectivity: int = 4) -> str:
    """Connected-component objects in the current frame (figure/ground). Free."""
    sess = store.load()
    if not sess.grid:
        return "no frame yet; `arcg look` after an action."
    # with_bg keeps every colour: -1 is absent from the 0-15 palette, so nothing
    # is treated as background.
    objs, bg = find_objects(np.asarray(sess.grid, np.int16),
                            background=-1 if with_bg else None,
                            connectivity=connectivity)
    return describe_objects(objs, bg)
