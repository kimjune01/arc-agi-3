"""QUARANTINED — a hand-written LS20 model. NOT shipped, NOT imported by the engine, the agent,
or the driver.

ARC-AGI-3 forbids problem-specific priors: the agent must learn each game from scratch, so this
LS20 knowledge (which colour is the avatar, that moves slide by 5, the energy bar, the locksmith
win-trigger) cannot be the agent's starting model. It is kept ONLY as (a) a reference for the
compile-from-arbor TARGET — what learning should eventually reproduce — and (b) a known engine for
testing the differential-test harness. If you find yourself importing this outside tests, stop.
"""

from __future__ import annotations

import numpy as np

CORRIDOR = 3
AVATAR = 12
TAIL = 9
BAR = 11
STEP = 5
PASSABLE = frozenset({CORRIDOR, 0, 1, 5, 11})
_DELTA = {"ACTION1": (-STEP, 0), "ACTION2": (STEP, 0),
          "ACTION3": (0, -STEP), "ACTION4": (0, STEP)}


def _unit_mask(grid: np.ndarray) -> np.ndarray:
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
    mask = _unit_mask(g)
    if not mask.any():
        return g
    ys, xs = np.nonzero(mask)
    nys, nxs = ys + dy, xs + dx
    h, w = g.shape
    if nys.min() < 0 or nys.max() >= h or nxs.min() < 0 or nxs.max() >= w:
        return g
    landing_outside_unit = ~mask[nys, nxs]
    dest = g[nys[landing_outside_unit], nxs[landing_outside_unit]]
    if not np.isin(dest, list(PASSABLE)).all():
        return g
    out = g.copy()
    out[ys, xs] = CORRIDOR
    out[nys, nxs] = g[ys, xs]
    return out


def _deplete_bar(g: np.ndarray) -> np.ndarray:
    cols = np.nonzero(g == BAR)[1]
    if cols.size == 0:
        return g
    out = g.copy()
    out[(g == BAR) & (np.arange(g.shape[1])[None, :] == cols.min())] = CORRIDOR
    return out


def step(grid, action: str, x: int | None = None, y: int | None = None) -> np.ndarray:
    g = np.asarray(grid, dtype=np.int16).copy()
    if action in _DELTA:
        dy, dx = _DELTA[action]
        return _deplete_bar(_slide(g, dy, dx))
    return g
