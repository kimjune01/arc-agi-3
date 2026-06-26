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
