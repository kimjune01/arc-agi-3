"""jotter content-addressed graph: dedup, transposition, revisit detection."""

import numpy as np

from arc_agi_3.jotter.graph import (
    EpMem, detect_counter, pending_edges, state_hash, trace, unique_edges,
)


def _g(seed):
    g = np.full((4, 4), 3, np.int16)
    g[0, 0] = seed
    return g.tolist()


def _t(before, action, after, x=None, y=None):
    return {"before": before, "action": action, "after": after, "x": x, "y": y}


def test_unique_edges_dedups_repeats():
    """The cheap filter's substrate: content-addressing collapses a repeated transition to one
    deduped edge, labelled by its FIRST occurrence — so the expensive translation never re-sees it."""
    A, B = _g(1), _g(2)
    rows = [_t(A, "ACTION1", B), _t(B, "ACTION2", A), _t(A, "ACTION1", B)]  # 3rd repeats the 1st
    u = unique_edges(rows)
    assert [e["idx"] for e in u] == [0, 1]                  # repeat dropped, first-occurrence order


def test_pending_excludes_spent():
    """Admission = deduped MINUS spent. A tombstoned edge-key drops out of the pending set."""
    A, B = _g(1), _g(2)
    rows = [_t(A, "ACTION1", B), _t(B, "ACTION2", A)]
    keys = [e["key"] for e in unique_edges(rows)]
    pend = pending_edges(rows, spent=frozenset({keys[0]}))
    assert [e["key"] for e in pend] == [keys[1]]            # the spent one is admitted no more


def test_spend_tombstones_idempotently_and_shrinks_pending(tmp_path):
    """End-to-end mechanical pipe (no LLM): spend writes a sidecar ledger, pending reflects it, and
    re-spending the same edge is a no-op (the trace itself is never touched)."""
    import json

    from arc_agi_3.jotter import cli
    A, B = _g(1), _g(2)
    corpus = tmp_path / "transitions.jsonl"
    corpus.write_text("\n".join(json.dumps(t) for t in [_t(A, "ACTION1", B), _t(B, "ACTION2", A)]))
    ledger = cli._ledger(corpus)

    assert "2 of 2" in cli.pending_report(corpus, ledger)           # nothing spent yet
    assert cli.spend(corpus, ledger, [0], "node-x").startswith("spent 1")
    assert "1 of 2" in cli.pending_report(corpus, ledger)           # admission set shrank
    assert cli.spend(corpus, ledger, [0], "node-x").startswith("spent 0")  # idempotent
    assert corpus.read_text().count("\n") == 1                      # grounded trace untouched (2 lines)


def test_evict_compresses_spent_episodes_keeping_the_action_log(tmp_path):
    """Stage 2 (compression): evict drops the GRIDS of consolidated episodes but keeps the action
    log + content-hashes. Un-spent episodes keep their grids. The whole corpus still loads."""
    import json

    from arc_agi_3.jotter import cli, graph
    A, B, C = _g(1), _g(2), _g(3)
    corpus = tmp_path / "transitions.jsonl"
    rows = [_t(A, "ACTION1", B), _t(B, "ACTION2", C), _t(A, "ACTION1", B)]  # step 2 repeats edge 0
    corpus.write_text("".join(json.dumps(t) + "\n" for t in rows))
    ledger = cli._ledger(corpus)

    cli.spend(corpus, ledger, [0], "node")                         # consolidate the A->B edge
    assert "evicted 2" in cli.evict(corpus, ledger, dry_run=False)  # BOTH A->B occurrences (0 and 2)

    after = [json.loads(l) for l in corpus.read_text().splitlines()]
    assert len(after) == 3                                          # action log length preserved
    assert graph.is_stub(after[0]) and graph.is_stub(after[2])      # spent edge -> grids dropped
    assert not graph.is_stub(after[1])                             # un-spent B->C keeps its grid
    m = graph.load(corpus)                                          # the deduped graph still loads
    assert len(m.order) == 3
    assert "1 of 2" in cli.pending_report(corpus, ledger)          # eviction doesn't disturb pending


def test_evict_preserves_identity_hashes(tmp_path):
    """Regression: re-detecting the counter from a shrunk row set shifted the hash mask and silently
    corrupted dedup. The PINNED counter keeps the trace's content-hashes identical across eviction."""
    import json

    from arc_agi_3.jotter import cli, graph
    A, B, C = _g(1), _g(2), _g(3)
    corpus = tmp_path / "transitions.jsonl"
    corpus.write_text("".join(json.dumps(t) + "\n" for t in [_t(A, "ACTION1", B), _t(B, "ACTION2", C)]))
    ledger = cli._ledger(corpus)
    before = [s["before"] for s in graph.trace([_t(A, "ACTION1", B), _t(B, "ACTION2", C)])["steps"]]

    cli.spend(corpus, ledger, [0], "n")
    cli.evict(corpus, ledger, dry_run=False)

    after_rows = [json.loads(l) for l in corpus.read_text().splitlines()]
    after = [s["before"] for s in graph.trace(after_rows, graph.load_counter(corpus))["steps"]]
    assert after == before                                          # identity unchanged by compression


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


def test_trace_is_content_addressed_and_ordered():
    """jotter trace is the series-evidence object: same play -> same id, reorder -> new id."""
    def g(seed):
        x = np.full((4, 4), 3, np.int16); x[0, 0] = seed; return x.tolist()
    rows = [
        {"action": "ACTION1", "before": g(1), "after": g(2)},
        {"action": "ACTION6", "x": 5, "y": 7, "before": g(2), "after": g(3)},
    ]
    t1 = trace(rows)
    assert t1["id"] is not None and t1["len"] == 2
    assert t1["initial"] == state_hash(g(1)) and t1["final"] == state_hash(g(3))
    assert trace(rows)["id"] == t1["id"]                 # reproducible (content-addressed)
    assert trace(list(reversed(rows)))["id"] != t1["id"] # order is load-bearing
    assert trace([])["id"] is None                       # empty corpus
