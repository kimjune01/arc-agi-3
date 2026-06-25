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


# --- objects (spatial edge detection) ------------------------------------
# Segment a frame into connected same-colour regions. This is the figure/ground
# primitive: it names the discrete things on the board (avatar, walls, tokens)
# so a policy can talk about "the 12-block" instead of raw cells. Background —
# the modal colour — is excluded by default since it's the ground, not a figure.

_NBRS4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_NBRS8 = _NBRS4 + ((-1, -1), (-1, 1), (1, -1), (1, 1))


@dataclass
class GridObject:
    color: int
    cells: int
    bbox: tuple[int, int, int, int]  # y0, x0, y1, x1

    @property
    def size(self) -> tuple[int, int]:
        y0, x0, y1, x1 = self.bbox
        return (y1 - y0 + 1, x1 - x0 + 1)


def _modal_color(arr: np.ndarray) -> int:
    values, counts = np.unique(arr, return_counts=True)
    return int(values[int(np.argmax(counts))])


def find_objects(grid: list[list[int]] | np.ndarray, *, background: int | None = None,
                 connectivity: int = 4) -> tuple[list[GridObject], int | None]:
    """Connected-component segmentation. Returns (objects, background_colour).

    Same-colour cells touching (4- or 8-connected) form one object. `background`
    defaults to the modal colour; pass an absent value (e.g. -1) to keep every
    colour. Deterministic: scan order fixes the object order (top-left first).
    """
    arr = np.asarray(grid, dtype=np.int16)
    if arr.size == 0:
        return [], None
    if background is None:
        background = _modal_color(arr)
    nbrs = _NBRS8 if connectivity == 8 else _NBRS4
    h, w = arr.shape
    seen = np.zeros(arr.shape, dtype=bool)
    objects: list[GridObject] = []
    for sy in range(h):
        for sx in range(w):
            if seen[sy, sx]:
                continue
            seen[sy, sx] = True
            color = int(arr[sy, sx])
            if color == background:
                continue
            stack = [(sy, sx)]
            y0 = y1 = sy
            x0 = x1 = sx
            count = 0
            while stack:
                cy, cx = stack.pop()
                count += 1
                y0, y1 = min(y0, cy), max(y1, cy)
                x0, x1 = min(x0, cx), max(x1, cx)
                for dy, dx in nbrs:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and int(arr[ny, nx]) == color:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            objects.append(GridObject(color=color, cells=count, bbox=(y0, x0, y1, x1)))
    return objects, background


def describe_objects(objects: list[GridObject], background: int | None, *,
                     max_items: int = 40) -> str:
    """Render objects grouped by colour, largest first, magnitude-honest."""
    if not objects:
        return f"no objects (background colour {background} fills the frame)"
    by_color: dict[int, list[GridObject]] = {}
    for o in objects:
        by_color.setdefault(o.color, []).append(o)
    head = (f"{len(objects)} objects across {len(by_color)} colours "
            f"(background {background} excluded):")
    lines = [head]
    shown = 0
    for color in sorted(by_color, key=lambda c: -sum(o.cells for o in by_color[c])):
        group = sorted(by_color[color], key=lambda o: -o.cells)
        lines.append(f"  colour {color}: {len(group)} object(s)")
        for o in group:
            if shown >= max_items:
                lines.append(f"  ...(+{len(objects) - shown} more objects)")
                return "\n".join(lines)
            y0, x0, y1, x1 = o.bbox
            h, w = o.size
            lines.append(f"    rows {y0}-{y1} cols {x0}-{x1} ({h}x{w}, {o.cells} cells)")
            shown += 1
    return "\n".join(lines)


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
