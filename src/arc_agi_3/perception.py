"""Perception: turn raw frames into something a policy (LLM or code) can read.

A frame is a 64x64 grid of colour indices 0-15. Two things matter for learning
an unknown game's mechanics:

1. A compact, lossless *rendering* of the current grid (one hex char per cell).
2. The *delta* from the previous frame — what changed when I acted. This is the
   single most informative signal: it localises the player, reveals what an
   action does, and exposes walls/collisions.

`Perception` is stateful: feed it each frame and it tracks the previous grid so
`observe()` can describe the change. It holds no policy — it only sees.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .structs import FrameData

_HEX = "0123456789abcdef"


def render_grid(grid: list[list[int]] | np.ndarray, *, blank: int = 0) -> str:
    """One hex char per cell, rows newline-separated. `blank` renders as '.'."""
    arr = np.asarray(grid)
    lines = []
    for row in arr:
        lines.append("".join("." if v == blank else _HEX[int(v) & 0xF] for v in row))
    return "\n".join(lines)


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    return int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())


@dataclass
class Delta:
    changed: int
    cells: list[tuple[int, int, int, int]]  # (y, x, old, new)
    bbox: tuple[int, int, int, int] | None

    def describe(self, *, max_cells: int = 12) -> str:
        if self.changed == 0:
            return "no change (action had no visible effect)"
        head = f"{self.changed} cells changed"
        if self.bbox:
            y0, x0, y1, x1 = self.bbox
            head += f", within rows {y0}-{y1}, cols {x0}-{x1}"
        shown = self.cells[:max_cells]
        detail = "; ".join(f"({y},{x}) {o}->{n}" for y, x, o, n in shown)
        more = "" if self.changed <= max_cells else f" ...(+{self.changed - max_cells} more)"
        return f"{head}: {detail}{more}"


def diff_grids(prev: np.ndarray, cur: np.ndarray) -> Delta:
    mask = prev != cur
    ys, xs = np.nonzero(mask)
    cells = [(int(y), int(x), int(prev[y, x]), int(cur[y, x])) for y, x in zip(ys, xs)]
    return Delta(changed=int(mask.sum()), cells=cells, bbox=_bbox(mask))


@dataclass
class Observation:
    step: int
    grid: np.ndarray
    delta: Delta | None
    palette: dict[int, int]            # colour -> cell count
    available_actions: list[str]
    state: str
    score: int

    def to_prompt(self, *, include_grid: bool = True) -> str:
        """Render as text for an LLM policy."""
        colours = ", ".join(f"{c}:{n}" for c, n in sorted(self.palette.items()))
        parts = [
            f"step {self.step} | state {self.state} | score {self.score}",
            f"colours present (value:count): {colours}",
            f"available actions: {', '.join(self.available_actions)}",
        ]
        if self.delta is not None:
            parts.append(f"since last action: {self.delta.describe()}")
        if include_grid:
            parts.append("grid (64x64, hex per cell, '.'=empty):")
            parts.append(render_grid(self.grid))
        return "\n".join(parts)


class Perception:
    """Stateful frame ingester. One instance per game session."""

    def __init__(self) -> None:
        self._prev: np.ndarray | None = None
        self.step = 0

    def reset(self) -> None:
        self._prev = None
        self.step = 0

    def observe(self, frame: FrameData) -> Observation:
        cur = np.asarray(frame.grid, dtype=np.int16)
        delta = None if self._prev is None or self._prev.shape != cur.shape else diff_grids(self._prev, cur)
        values, counts = np.unique(cur, return_counts=True)
        palette = {int(v): int(n) for v, n in zip(values, counts)}
        obs = Observation(
            step=self.step,
            grid=cur,
            delta=delta,
            palette=palette,
            available_actions=[a.name for a in frame.available_actions],
            state=frame.state.value,
            score=frame.score,
        )
        self._prev = cur
        self.step += 1
        return obs
