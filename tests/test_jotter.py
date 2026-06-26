"""jotter content-addressed graph: dedup, transposition, revisit detection."""

import numpy as np

from arc_agi_3.jotter.graph import EpMem, state_hash


def _g(seed):
    g = np.full((4, 4), 3, np.int16)
    g[0, 0] = seed
    return g.tolist()


def test_same_grid_hashes_identically():
    assert state_hash(_g(1)) == state_hash(_g(1))
    assert state_hash(_g(1)) != state_hash(_g(2))


def test_dedup_and_transposition():
    A, B, C = _g(1), _g(2), _g(3)
    m = EpMem()
    # two different states (A, B) both transition to the SAME state C, by different routes
    m.ingest(A, "ACTION1", None, None, C)
    m.ingest(B, "ACTION2", None, None, C)
    # C stored once despite two arrivals; A, B, C = 3 unique states
    assert len(m.states) == 3
    assert state_hash(C) in m.transpositions()  # reached >1 way


def _bar_grid(bar_cols, pickup=True):
    """8x8: avatar top-left, an optional maze pickup (small 11, high up), a bottom bar."""
    g = np.full((8, 8), 3, np.int16)   # corridor
    g[0, 0] = 12                        # avatar
    if pickup:
        g[3, 3] = 11; g[3, 4] = 11     # energy pickup (kept)
    for c in bar_cols:
        g[7, c] = 11                   # bottom energy bar (masked)
    return g.tolist()


def test_canonical_hash_ignores_bar_depletion():
    # same place, different move-counter (bar depleted two columns -> they read as corridor)
    full = _bar_grid([1, 2, 3, 4, 5])
    depleted = _bar_grid([3, 4, 5])
    assert state_hash(full) == state_hash(depleted)


def test_canonical_hash_keeps_pickup():
    # collecting a maze pickup IS salient — must change the hash
    assert state_hash(_bar_grid([1, 2, 3, 4, 5], pickup=True)) \
        != state_hash(_bar_grid([1, 2, 3, 4, 5], pickup=False))


def test_revisit_detection():
    A, B = _g(1), _g(2)
    m = EpMem()
    m.ingest(A, "ACTION1", None, None, B)
    m.ingest(B, "ACTION2", None, None, A)  # returns to A
    assert state_hash(A) in m.revisits()


def test_has():
    A, B = _g(1), _g(2)
    m = EpMem()
    m.ingest(A, "ACTION1", None, None, B)
    assert m.has(state_hash(A)) and m.has(state_hash(B))
    assert not m.has("deadbeef00")


def test_audit_gapless_vs_gap():
    A, B, C = _g(1), _g(2), _g(3)
    good = EpMem()
    good.ingest(A, "ACTION1", None, None, B, spent=1)
    good.ingest(B, "ACTION1", None, None, C, spent=2)
    a = good.audit()
    assert a["gapless"] and a["count_matches_last_stamp"] and a["transitions"] == 2

    gap = EpMem()
    gap.ingest(A, "ACTION1", None, None, B, spent=1)
    gap.ingest(B, "ACTION1", None, None, C, spent=3)  # action 2 went unrecorded
    g = gap.audit()
    assert not g["gapless"]                      # the drop is caught
    assert not g["count_matches_last_stamp"]     # 2 transitions but last stamp 3
