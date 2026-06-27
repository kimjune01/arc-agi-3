"""dagger Action DAG — sanity over the COMMITTED outer contracts only (DAGGER.md §interface).

Backed by an in-memory jotter SQLite store. The deferred parts (matcher tolerance, the simmer
commuting check) are deliberately NOT asserted: this pins the committed shape, not the impl's
unverified judgment.
"""

import pytest

from arc_agi_3 import dagger as dg
from arc_agi_3.jotter import db


def _conn():
    return db.connect(":memory:")


def test_init_seeds_apex_and_one_leaf_per_action():
    c = _conn()
    dg.init(c, ["ACTION1", "ACTION2", "ACTION6"])
    rows = db.nodes(c)
    assert len(rows) == 4                                  # apex + 3 leaves, determined
    assert dg.get(c, "dagger:win-game").post == dg.WIN
    leaves = [r for r in rows if r["kind"] == "leaf"]
    assert sorted(r["action"] for r in leaves) == ["ACTION1", "ACTION2", "ACTION6"]


def test_plan_misses_to_hole_then_hits_after_decompose():
    c = _conn()
    dg.init(c, ["ACTION1"])
    assert isinstance(dg.plan(c, "win game"), dg.Hole)     # apex undecomposed -> JIT miss
    dg.decompose(c, "win-recipe", "win game", ["ACTION1"], "sequence")
    assert isinstance(dg.plan(c, "WIN  GAME"), dg.Node)    # normalized exact hit


def test_put_idempotent_and_get_resolves_ref():
    c = _conn()
    n = dg.decompose(c, "open-door", "open door", ["ACTION1"], "sequence")
    before = len(db.nodes(c))
    assert dg.put(c, n).anchor == n.anchor and len(db.nodes(c)) == before   # no new node
    assert dg.get(c, n.ref()).anchor == "open-door"
    assert dg.get(c, "dagger:nope") is None                                 # MISS is data


def test_status_ratchets_by_domination_never_downgrades():
    c = _conn()
    base = dg.Node(anchor="x", post="p", children=("ACTION1",), mode="sequence")  # open
    dg.put(c, base)
    dg.put(c, dg.Node(anchor="x", post="p", children=("ACTION1",), mode="sequence", status="killed"))
    assert dg.get(c, "x").status == "killed"               # ratcheted up
    dg.put(c, base)                                        # re-put open
    assert dg.get(c, "x").status == "killed"               # never downgrades


def test_merge_dominates_on_status():
    a, b = _conn(), _conn()
    node = dg.Node(anchor="x", post="p", children=("ACTION1",), mode="sequence")
    dg.put(a, node)                                                            # open in a
    dg.put(b, dg.Node(**{**node.__dict__, "status": "killed"}))                # killed in b
    dg.merge(a, b)
    assert dg.get(a, "x").status == "killed"               # killed wins the join


def test_decompose_rejects_bad_mode():
    with pytest.raises(ValueError):
        dg.decompose(_conn(), "a", "g", ["ACTION1"], "nonsense")


def test_render_lists_the_graph():
    c = _conn()
    dg.init(c, ["ACTION1"])
    md = dg.render(c)
    assert md.startswith("# dagger graph") and "win-game" in md and "ACTION1" in md
