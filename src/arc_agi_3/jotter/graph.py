"""The content-addressed state graph. Pure data structure built from the corpus."""

from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

import numpy as np


_MASK = -1    # sentinel for masked-out cells (value irrelevant, only that it's constant)


def detect_counter(states) -> frozenset:
    """Find the on-board move-counter from the visited-state SEQUENCE, so it can be projected
    out before hashing. A move-counter is a thin strip that ticks once per action (deplete, or
    refill on reset); hashing the raw grid would then make every state spuriously unique and
    defeat revisit/transposition detection (run4: the avatar reset to level-start ~11x, all
    reported novel; run5/tn36: a config reached 5x, all reported novel).

    Game-agnostic by construction: it keys on the BEHAVIOUR (a thin band touched by ~every
    transition), not a hardcoded colour/position. LS20's counter was a colour-11 strip on the
    bottom; tn36's a colour-9 strip on top — both are the thin line whose diff fires every
    action. Returns the bbox of cells to mask (covering the depleted track), or empty if none.
    """
    S = [np.asarray(s, dtype=np.int16) for s in states]
    if len(S) < 4 or S[0].ndim != 2:
        return frozenset()
    h, w = S[0].shape
    diffs = [S[i] != S[i + 1] for i in range(len(S) - 1)]
    everdiff = np.zeros((h, w), bool)
    for d in diffs:
        everdiff |= d
    n = len(diffs)
    thresh = max(3, int(0.9 * n))   # the counter ticks on (nearly) every action

    def bands(hit: list[int]) -> list[list[int]]:
        out: list[list[int]] = []
        for i in sorted(hit):
            if out and i == out[-1][-1] + 1:
                out[-1].append(i)
            else:
                out.append([i])
        return out

    rows_hit = [y for y in range(h) if sum(int(d[y].any()) for d in diffs) >= thresh]
    cols_hit = [x for x in range(w) if sum(int(d[:, x].any()) for d in diffs) >= thresh]
    best = None   # (band_thickness, bbox)
    for band in bands(rows_hit):
        if len(band) > 3:
            continue                                   # a counter strip is thin
        cols = np.argwhere(everdiff[band, :].any(axis=0)).flatten()
        if cols.size and (best is None or len(band) < best[0]):
            best = (len(band), (min(band), int(cols.min()), max(band), int(cols.max())))
    for band in bands(cols_hit):
        if len(band) > 3:
            continue
        rows = np.argwhere(everdiff[:, band].any(axis=1)).flatten()
        if rows.size and (best is None or len(band) < best[0]):
            best = (len(band), (int(rows.min()), min(band), int(rows.max()), max(band)))
    if best is None:
        return frozenset()
    y0, x0, y1, x1 = best[1]
    return frozenset((y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))


def state_hash(grid, counter=frozenset()) -> str:
    """Stable short id for a state = hash of the grid with the move-counter cells masked, so the
    same configuration hashes identically regardless of the counter. `counter` is the cell set
    from `detect_counter` (empty = hash the raw grid)."""
    arr = np.asarray(grid, dtype=np.int16).copy()
    for (y, x) in counter:
        arr[y, x] = _MASK
    return hashlib.sha1(arr.tobytes()).hexdigest()[:10]


class EpMem:
    """States deduped by content; edges keyed by (from, action). Transpositions
    collapse to one node because identical grids hash identically."""

    def __init__(self, counter=frozenset()) -> None:
        self.counter = counter                       # move-counter cells masked before hashing
        self.states: dict[str, list] = {}            # hash -> grid (stored once)
        self.edges: dict[tuple, str] = {}            # (from, action, x, y) -> to
        self.preds: dict[str, set] = {}              # to -> {(from, action)}  (how reached)
        self.order: list[tuple[str, str, str]] = []  # trajectory: (from, action, to)
        self.spents: list[int | None] = []           # piper's budget stamp per transition

    def ingest(self, before, action: str, x, y, after, spent=None) -> tuple[str, str]:
        hb, ha = state_hash(before, self.counter), state_hash(after, self.counter)
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
    if not path.exists():
        return EpMem()
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        return EpMem()
    # Detect the move-counter from the visited-state sequence, then hash with it masked.
    states = [rows[0]["before"]] + [t["after"] for t in rows]
    m = EpMem(counter=detect_counter(states))
    for t in rows:
        m.ingest(t["before"], t["action"], t.get("x"), t.get("y"), t["after"],
                 spent=t.get("spent"))
    return m


def trace(rows: list) -> dict:
    """A content-addressed TRACE: the ordered action series as a first-class evidence object.

    The series-hypothesis unit. Rather than leaning on a git commit RANGE (whose meaning shifts
    under rewrite/merge/shallow-clone), the trace is hashed directly: re-recording the same play
    yields the same id, so it is a stable, reproducible key. States use the same counter-masked
    hash as the dedup graph, so trace identity agrees with state identity.

    Returns `{id, initial, steps:[{action,x,y,before,after}], final, len}`; id is None if empty.
    NOTE: this is the EVIDENCE layer only (what happened, content-addressed). Belief about it
    (verdicts, credence) is a derived, non-monotone query that lives above and stays deferred.
    """
    if not rows:
        return {"id": None, "initial": None, "steps": [], "final": None, "len": 0}
    states = [rows[0]["before"]] + [t["after"] for t in rows]
    counter = detect_counter(states)
    steps = [{"action": t["action"], "x": t.get("x"), "y": t.get("y"),
              "before": state_hash(t["before"], counter),
              "after": state_hash(t["after"], counter)} for t in rows]
    core = {"initial": steps[0]["before"], "steps": steps, "final": steps[-1]["after"]}
    tid = hashlib.sha1(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    return {"id": tid, **core, "len": len(steps)}


def edge_key(hb: str, action: str, x, y, ha: str) -> str:
    """Canonical content-addressed id for a transition (deduped EDGE): masked from-hash, action,
    coord, to-hash. Stable across re-indexing — the spent-ledger keys on this, not on step index."""
    return f"{hb}:{action}:{'' if x is None else x}:{'' if y is None else y}:{ha}"


def unique_edges(rows: list, counter=frozenset()) -> list[dict]:
    """The DEDUPED episode set in first-occurrence order — the cheap admission filter's input.
    Content-addressing collapses repeats/transpositions for free, so a transition seen at steps
    3,4,8 appears once (labelled by its first index 3). Each entry: {idx, before, action, x, y,
    after, key}. The consolidation pipe's `map` ranges over THIS, not the raw repeated corpus."""
    seen: set[str] = set()
    out: list[dict] = []
    for i, t in enumerate(rows):
        hb, ha = state_hash(t["before"], counter), state_hash(t["after"], counter)
        k = edge_key(hb, t["action"], t.get("x"), t.get("y"), ha)
        if k in seen:
            continue
        seen.add(k)
        out.append({"idx": i, "before": hb, "action": t["action"],
                    "x": t.get("x"), "y": t.get("y"), "after": ha, "key": k})
    return out


def pending_edges(rows: list, counter=frozenset(), spent: frozenset = frozenset()) -> list[dict]:
    """The ADMISSION SET: deduped edges whose content-key is NOT yet in the spent ledger. This is
    the cheap mechanical filter — the expensive LLM translation ranges over only these, not the
    whole corpus (doing it all in one pass re-judges what's already consolidated)."""
    return [e for e in unique_edges(rows, counter) if e["key"] not in spent]


def transition_diff(before, after):
    """The SPATIAL delta of one recorded transition, via piper's perception (`diff_grids`) — WHAT
    changed and where, not how many. Returns a perception Delta (`.changed`, `.describe()`)."""
    from ..perception import diff_grids
    return diff_grids(np.asarray(before, np.int16), np.asarray(after, np.int16))


def diffs(rows: list) -> list:
    """Per-transition spatial deltas over the whole trace: the position story, the spatial twin of
    `effects` (the count story). Movement is count-conserved, so it shows HERE but is invisible to
    `effects` — this is how the agent recovers an action's effect from the trace instead of
    re-spending budget to rediscover it. Returns [(i, action, x, y, Delta), ...]."""
    return [(i, t["action"], t.get("x"), t.get("y"), transition_diff(t["before"], t["after"]))
            for i, t in enumerate(rows)]


def effects(rows: list) -> dict:
    """Grounded per-action effects, straight from the recorded transitions: for each action, the
    distribution of per-colour cell-count deltas (after − before). This answers the **resource /
    quantity facts** a driver mis-estimates — the bar depletes, tokens are consumed, score moves
    — from the record rather than from a model or a guess. It is deliberately COUNT-based, not
    spatial: *where* things move is simmer's job; *how many* of each colour change is jotter's
    ground truth (and a non-constant distribution, e.g. `11: -2×11, -4×24`, exposes a rate that
    isn't fixed — exactly the fact an estimate gets wrong).

    Returns `{action: {colour: Counter(delta -> occurrences)}}`, only non-zero deltas.
    """
    out: dict = {}
    for t in rows:
        a = t.get("action")
        b = np.asarray(t["before"], np.int16)
        af = np.asarray(t["after"], np.int16)
        for c in set(np.unique(b).tolist()) | set(np.unique(af).tolist()):
            d = int((af == c).sum()) - int((b == c).sum())
            if d:
                out.setdefault(a, {}).setdefault(int(c), collections.Counter())[d] += 1
    return out
