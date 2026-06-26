"""simmer's engine — the hand-edited model. EDIT THIS FILE as you learn mechanics.

Each mechanic is a pure rule; `step` dispatches to them. The goal is for `step` to
reproduce piper's recorded transitions (`simmer test`). A rule that's wrong shows up
as a localized mismatch — refine it and re-test. PURE: no I/O, no mutation of inputs.

Hypotheses encoded so far (LS20, refined against the corpus 2026-06-25):
- ACTION1-4 slide the avatar (colour 12) + its connected tail (colour 9) by 5 cells,
  BUT only if every destination cell is PASSABLE; a move into a wall (4) is blocked
  (the avatar stays). Refuted the naive "always 5" via `simmer test` (the left move ran
  into void). Vacated cells become corridor.
- PASSABLE = corridor (3) plus the collectibles the avatar was WITNESSED sliding through
  in run2's corpus: the token (0/1) and the box wall (5). Refined from "corridor only"
  after `simmer test` localized three mispredicts where the avatar passed a collectible
  the old rule called blocking. Witnessed-passable only — 4 still blocks; 11 (bar) is
  NOT asserted passable (never witnessed entering it). This models REACHABILITY (what a
  planner needs); it deliberately does NOT model collectible STATE effects (the token,
  once overlapped, repaints a small carried-pattern HUD in the bottom-left box). That
  effect is instance-specific and reachability-irrelevant, so it's left unmodelled — the
  residual `simmer test` miss it leaves is expected, not a bug to chase.
- Every move action depletes the energy bar (colour 11) by one column, from the left,
  whether or not the avatar actually moved (it still costs energy). Localized by the
  2-cell residual the slide rule left behind.
"""

from __future__ import annotations

import numpy as np

CORRIDOR = 3
AVATAR = 12
TAIL = 9
BAR = 11
STEP = 5

# Cells the avatar+tail unit may slide INTO. Corridor plus the collectibles witnessed
# passable in run2's corpus (token 0/1, box wall 5). Witnessed-only: 4 blocks; the bar
# (11) is not asserted passable. Widen only when a transition witnesses a new colour.
PASSABLE = frozenset({CORRIDOR, 0, 1, 5})

# direction deltas for the four move actions (dy, dx)
_DELTA = {"ACTION1": (-STEP, 0), "ACTION2": (STEP, 0),
          "ACTION3": (0, -STEP), "ACTION4": (0, STEP)}


def _unit_mask(grid: np.ndarray) -> np.ndarray:
    """The avatar (12) cells plus the 9-tail 4-connected to them (the moving unit)."""
    mask = grid == AVATAR
    if not mask.any():
        return mask
    h, w = grid.shape
    frontier = list(zip(*np.nonzero(mask)))
    while frontier:
        y, x = frontier.pop()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and grid[ny, nx] == TAIL:
                mask[ny, nx] = True
                frontier.append((ny, nx))
    return mask


def _slide(g: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Move the avatar+tail unit by (dy,dx) iff every destination cell outside the unit
    is clear corridor; otherwise blocked (no move)."""
    mask = _unit_mask(g)
    if not mask.any():
        return g
    ys, xs = np.nonzero(mask)
    nys, nxs = ys + dy, xs + dx
    h, w = g.shape
    if nys.min() < 0 or nys.max() >= h or nxs.min() < 0 or nxs.max() >= w:
        return g  # boundary
    landing_outside_unit = ~mask[nys, nxs]
    dest = g[nys[landing_outside_unit], nxs[landing_outside_unit]]
    if not np.isin(dest, list(PASSABLE)).all():
        return g  # a wall (anything not PASSABLE) blocks the slide
    out = g.copy()
    out[ys, xs] = CORRIDOR     # vacate
    out[nys, nxs] = g[ys, xs]  # place the unit one step over
    return out


def _deplete_bar(g: np.ndarray) -> np.ndarray:
    """Remove the leftmost remaining column of the energy bar (colour 11)."""
    cols = np.nonzero(g == BAR)[1]
    if cols.size == 0:
        return g
    out = g.copy()
    out[(g == BAR) & (np.arange(g.shape[1])[None, :] == cols.min())] = CORRIDOR
    return out


def step(grid, action: str, x: int | None = None, y: int | None = None) -> np.ndarray:
    """Apply one action to the grid, return the successor grid. Pure."""
    g = np.asarray(grid, dtype=np.int16).copy()
    if action in _DELTA:
        dy, dx = _DELTA[action]
        return _deplete_bar(_slide(g, dy, dx))  # a move costs energy even if blocked
    return g  # unknown action: identity (no model yet)
