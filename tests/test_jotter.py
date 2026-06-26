"""jotter content-addressed graph: dedup, transposition, revisit detection."""

import numpy as np

from arc_agi_3.jotter.graph import EpMem, detect_counter, state_hash


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


def _counter_grid(strip_len, colour=9, marker=False):
    """8x8: a thin bottom strip (the move-counter) of `strip_len` cells, + optional salient cell.
    No hardcoded colour/position — detection keys on the depletion behaviour across a sequence."""
    g = np.full((8, 8), 3, np.int16)
    g[7, :strip_len] = colour          # the counter strip, ticking down one cell per action
    if marker:
        g[3, 3] = 1                    # a salient game cell (e.g. a placed marker)
    return g.tolist()


def test_detect_counter_masks_depletion():
    # a run where the bottom strip depletes one cell per action — detect it from the sequence
    seq = [_counter_grid(5), _counter_grid(4), _counter_grid(3), _counter_grid(2)]
    counter = detect_counter(seq)
    assert counter                                  # found the counter strip
    # two states differing ONLY in counter length hash identically once it's masked
    assert state_hash(_counter_grid(5), counter) == state_hash(_counter_grid(2), counter)


def test_detect_counter_keeps_salient_change():
    seq = [_counter_grid(5), _counter_grid(4), _counter_grid(3), _counter_grid(2)]
    counter = detect_counter(seq)
    # a real game change (placing a marker, off the counter strip) is NOT masked
    assert state_hash(_counter_grid(3, marker=False), counter) \
        != state_hash(_counter_grid(3, marker=True), counter)


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


def test_effects_grounded_counts():
    """jotter effects reports per-action per-colour count deltas from the record (resource facts)."""
    from arc_agi_3.jotter.graph import effects
    def g(bar):
        x = np.full((4, 4), 3, np.int16); x[0, :bar] = 11; return x.tolist()
    rows = [
        {"action": "ACTION1", "before": g(4), "after": g(2)},   # colour 11: -2 (3: +2)
        {"action": "ACTION1", "before": g(2), "after": g(0)},   # colour 11: -2
        {"action": "ACTION2", "before": g(4), "after": g(1)},   # colour 11: -3
    ]
    e = effects(rows)
    assert e["ACTION1"][11][-2] == 2          # ACTION1 depletes colour-11 by 2, witnessed twice
    assert e["ACTION1"][3][+2] == 2           # vacated cells become corridor (3)
    assert e["ACTION2"][11][-3] == 1
    assert 0 not in e.get("ACTION1", {}).get(11, {})   # only non-zero deltas recorded
