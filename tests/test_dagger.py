"""dagger Action DAG — sanity over the COMMITTED outer contracts only (DAGGER.md §interface).

The deferred parts (the matcher's tolerance, the simmer commuting check in `decompose`) are
deliberately NOT asserted: this pins the shape we committed, not the impl's unverified judgment.
"""

import dataclasses

from arc_agi_3 import dagger as dg


def test_init_seeds_apex_and_one_leaf_per_action():
    d = dg.init(["ACTION1", "ACTION2", "ACTION6"])
    assert len(d.nodes) == 4                       # apex + 3 leaves, determined
    assert any(n.post == dg.WIN for n in d.nodes.values())
    leaves = [n for n in d.nodes.values() if n.is_leaf]
    assert sorted(n.action for n in leaves) == ["ACTION1", "ACTION2", "ACTION6"]


def test_plan_misses_to_hole_then_hits_after_decompose():
    d = dg.init(["ACTION1"])
    assert isinstance(dg.plan(d, "win game"), dg.Hole)      # apex undecomposed -> JIT miss
    dg.decompose(d, "win game", ["c1", "c2"], "sequence")
    assert isinstance(dg.plan(d, "WIN  GAME"), dg.Node)     # normalized exact hit


def test_put_idempotent_and_get_resolves_ref():
    d = dg.init([])
    n = dg.decompose(d, "open door", ["c1"], "sequence")
    before = len(d.nodes)
    assert dg.put(d, n).id == n.id and len(d.nodes) == before   # no new node
    assert dg.get(d, n.ref()).id == n.id
    assert dg.get(d, "dagger:nope") is None                     # MISS is data, not error


def test_identity_excludes_status_so_a_kill_keeps_the_ref():
    a = dg.Node(post="open door", children=("c1",), mode="sequence")
    killed = dataclasses.replace(a, status="killed")
    assert a.id == killed.id                                    # status is outside the id key


def test_distinct_prose_distinct_id_matcher_never_dedups():
    # exact equality for identity: two goals the matcher MIGHT judge equal stay distinct here.
    assert dg.Node(post="block adjacent to wall").id != dg.Node(post="block left-aligned").id


def test_merge_commutative_and_idempotent_under_status_conflict():
    base = dg.Node(post="open door", children=("c1",), mode="sequence")   # open
    killed = dataclasses.replace(base, status="killed")
    A, B = dg.Dag(), dg.Dag()
    dg.put(A, base)
    dg.put(B, killed)
    ab, ba = dg.merge(A, B), dg.merge(B, A)
    assert ab.nodes[base.id].status == "killed" == ba.nodes[base.id].status  # domination, both orders
    assert set(dg.merge(ab, ab).nodes) == set(ab.nodes)                      # idempotent


def test_decompose_rejects_bad_mode():
    import pytest
    with pytest.raises(ValueError):
        dg.decompose(dg.Dag(), "g", ["c1"], "nonsense")
