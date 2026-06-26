"""The content-addressed state graph. Pure data structure built from the corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


CORRIDOR = 3
BAR = 11      # the energy bar (a monotone move-counter)
LIVES = 8     # the lives counter (also monotone)
_MASK = -1    # sentinel for canonicalised-out cells (value irrelevant, only that it's constant)


def _components(arr: np.ndarray, color: int) -> list[list[tuple[int, int]]]:
    """4-connected components of `color`, each a list of (y, x) cells."""
    h, w = arr.shape
    seen = np.zeros(arr.shape, bool)
    out: list[list[tuple[int, int]]] = []
    for sy in range(h):
        for sx in range(w):
            if seen[sy, sx] or arr[sy, sx] != color:
                continue
            stack = [(sy, sx)]; seen[sy, sx] = True; cells = []
            while stack:
                y, x = stack.pop(); cells.append((y, x))
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and arr[ny, nx] == color:
                        seen[ny, nx] = True; stack.append((ny, nx))
            out.append(cells)
    return out


def _canonical(grid) -> np.ndarray:
    """Project out the on-board move-counters before hashing.

    The energy bar (colour 11) loses one column per move and refills on reset, so hashing the
    raw grid makes every state spuriously unique — defeating revisit/transposition detection
    (run4: the avatar reset to level-start ~11x, every one reported as novel). Mask the bar's
    whole ROW BAND, not just its live cells: the depleted columns read as corridor (3), so the
    band must include 3 to stay invariant under depletion. The bar is the BOTTOMMOST 11-
    component (maze 11-clusters are energy pickups, higher up — salient state, kept). The lives
    counter (colour 8, in the same band) is masked too, so a reset (which decrements it) still
    matches level-start. LS20-specific by design; widen when a second game needs it.
    """
    arr = np.asarray(grid, dtype=np.int16).copy()
    comps = _components(arr, BAR)
    if comps:
        bar = max(comps, key=lambda c: max(y for y, _ in c))   # bottommost = the bar
        for y in {y for y, _ in bar}:
            row = arr[y]
            row[(row == BAR) | (row == CORRIDOR) | (row == LIVES)] = _MASK
    return arr


def state_hash(grid) -> str:
    """Stable short id for a state = hash of its CANONICAL grid (move-counters projected out,
    so the same place revisited hashes identically). See `_canonical`."""
    return hashlib.sha1(_canonical(grid).tobytes()).hexdigest()[:10]


class EpMem:
    """States deduped by content; edges keyed by (from, action). Transpositions
    collapse to one node because identical grids hash identically."""

    def __init__(self) -> None:
        self.states: dict[str, list] = {}            # hash -> grid (stored once)
        self.edges: dict[tuple, str] = {}            # (from, action, x, y) -> to
        self.preds: dict[str, set] = {}              # to -> {(from, action)}  (how reached)
        self.order: list[tuple[str, str, str]] = []  # trajectory: (from, action, to)
        self.spents: list[int | None] = []           # piper's budget stamp per transition

    def ingest(self, before, action: str, x, y, after, spent=None) -> tuple[str, str]:
        hb, ha = state_hash(before), state_hash(after)
        self.states.setdefault(hb, before)
        self.states.setdefault(ha, after)
        self.edges[(hb, action, x, y)] = ha
        self.preds.setdefault(ha, set()).add((hb, action))
        self.order.append((hb, action, ha))
        self.spents.append(spent)
        return hb, ha

    def audit(self) -> dict:
        """Reconcile jotter against piper via the budget stamps. Gapless stamps mean
        every piper action was recorded; a gap means a transition was dropped."""
        stamps = [s for s in self.spents if s is not None]
        gapless = bool(stamps) and stamps == list(range(stamps[0], stamps[0] + len(stamps)))
        return {
            "transitions": len(self.order),
            "stamped": len(stamps),
            "stamp_range": (stamps[0], stamps[-1]) if stamps else None,
            "gapless": gapless,
            "count_matches_last_stamp": bool(stamps) and len(self.order) == stamps[-1],
        }

    def has(self, h: str) -> bool:
        return h in self.states

    def transpositions(self) -> list[str]:
        """States reached via more than one distinct (from, action) — same place,
        different route. The reason content-addressing beats history-keying."""
        return [h for h, p in self.preds.items() if len(p) > 1]

    def revisits(self) -> list[str]:
        """States the trajectory ENTERS more than once (a genuine return/cycle).
        Computed on the visited-state sequence, so a linear chain has none (its
        joints — after_i == before_{i+1} — are linkage, not returns)."""
        if not self.order:
            return []
        visited = [self.order[0][0]] + [ha for _, _, ha in self.order]
        seen, repeated = set(), set()
        for h in visited:
            if h in seen:
                repeated.add(h)
            seen.add(h)
        return sorted(repeated)


def load(path: Path) -> EpMem:
    m = EpMem()
    if not path.exists():
        return m
    for line in path.read_text().splitlines():
        if line.strip():
            t = json.loads(line)
            m.ingest(t["before"], t["action"], t.get("x"), t.get("y"), t["after"],
                     spent=t.get("spent"))
    return m
