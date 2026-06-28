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
    assert len(rows) == 4                                  # apex + 3 leaves (deposit is a JIT miss)
    apex = dg.get(c, "dagger:win-game")
    assert apex.post == dg.WIN
    assert apex.children == (dg.DEPOSIT_ANCHOR,)           # win-down spine pre-baked at init
    assert dg.get(c, dg.DEPOSIT_ANCHOR) is None            # the per-level BODY stays a HOLE
    leaves = [r for r in rows if r["kind"] == "leaf"]
    assert sorted(r["action"] for r in leaves) == ["ACTION1", "ACTION2", "ACTION6"]


def test_apex_spine_prebaked_body_is_jit():
    c = _conn()
    dg.init(c, ["ACTION1"])
    apex = dg.plan(c, "win game")
    assert isinstance(apex, dg.Node)                       # apex HITS: spine baked (win = repeat deposit)
    assert apex.children == (dg.DEPOSIT_ANCHOR,)
    assert isinstance(dg.plan(c, dg.DEPOSIT_POST), dg.Hole)   # the BODY is the JIT miss now
    dg.decompose(c, dg.DEPOSIT_ANCHOR, dg.DEPOSIT_POST, ["ACTION1"], "sequence")
    assert isinstance(dg.plan(c, dg.DEPOSIT_POST), dg.Node)   # body grown -> hit


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


# --- attribution gate: dream freely (open), but a verdict must cite its episodes ----------------
def test_open_node_is_speculative_and_needs_no_evidence():
    c = _conn()
    n = dg.decompose(c, "hunch", "ACTION4 probably moves right", ["ACTION4"], "sequence")  # open
    assert n.status == "open" and n.evidence == () and n.provenance == "speculative"
    assert "speculative" in dg.render(c)                      # marked, not hidden


def test_apex_is_speculative_until_a_winning_episode():
    c = _conn()
    dg.init(c, ["ACTION1"])
    assert dg.get(c, "dagger:win-game").provenance == "speculative"   # no episode wins yet


def test_verdict_without_evidence_is_rejected():
    c = _conn()
    with pytest.raises(ValueError):                           # a killed nogood is a verdict
        dg.decompose(c, "x", "ACTION1 then ACTION2 round-trips", ["ACTION1", "ACTION2"],
                     "sequence", status="killed")
    with pytest.raises(ValueError):                           # so is a live positive
        dg.decompose(c, "y", "ACTION1 moves up", ["ACTION1"], "sequence", status="live")


def test_causal_verdict_requires_a_contrast_pair():
    c = _conn()
    causal = "vertical blocked when colour-9 adjacent below cursor"
    with pytest.raises(ValueError):                           # one episode can't isolate a cause
        dg.decompose(c, "blk", causal, ["ACTION1", "ACTION2"], "conjunction",
                     status="killed", evidence=["5695"])
    n = dg.decompose(c, "blk", causal, ["ACTION1", "ACTION2"], "conjunction",
                     status="killed", evidence=["b765", "5695"])   # the pair lands it
    assert n.status == "killed" and n.evidence == ("b765", "5695") and n.provenance == "grounded"


def test_noncausal_verdict_accepts_a_single_episode():
    c = _conn()
    n = dg.decompose(c, "up5", "ACTION1 moves the block up 5 rows", ["ACTION1"],
                     "sequence", status="live", evidence=["0"])
    assert n.provenance == "grounded" and n.evidence == ("0",)


def test_apex_is_unkillable_the_root_goal_stays_reachable():
    c = _conn()
    dg.init(c, ["ACTION1"])
    with pytest.raises(ValueError):                           # decompose may not target the apex
        dg.decompose(c, dg.WIN_ANCHOR, "win game", ["ACTION1"], "sequence",
                     status="killed", evidence=["0", "1"])
    with pytest.raises(ValueError):                           # nor any direct put off `open`
        dg.put(c, dg.Node(anchor=dg.WIN_ANCHOR, post=dg.WIN, status="killed"))
    assert dg.get(c, "dagger:win-game").status == "open"      # apex untouched
    # winning stays plannable: the apex (with its pre-baked spine) is a HIT, never killed-away
    assert isinstance(dg.plan(c, "win game"), dg.Node)
    # the per-level recipe lives under deposit-one-point (the spine's body), matched on its post
    dg.decompose(c, dg.DEPOSIT_ANCHOR, dg.DEPOSIT_POST, ["ACTION1"], "sequence", status="live",
                 evidence=["0"])
    assert isinstance(dg.plan(c, dg.DEPOSIT_POST), dg.Node)


def test_promotion_carries_evidence_dream_then_ground():
    c = _conn()
    causal = "vertical blocked when colour-9 adjacent below"
    dg.decompose(c, "blk", causal, ["ACTION1", "ACTION2"], "conjunction")   # open dream, no evidence
    assert dg.get(c, "dagger:blk").provenance == "speculative" and dg.get(c, "dagger:blk").evidence == ()
    dg.decompose(c, "blk", causal, ["ACTION1", "ACTION2"], "conjunction",   # promote to a verdict...
                 status="killed", evidence=["b765", "5695"])
    n = dg.get(c, "dagger:blk")
    assert n.status == "killed" and n.evidence == ("b765", "5695")          # ...and the grounding STICKS
    assert n.children == ("ACTION1", "ACTION2")


def test_evidence_dedups_and_round_trips_through_the_store():
    c = _conn()
    dg.decompose(c, "pair", "horizontal actions drag colour-9 with cursor", ["ACTION3", "ACTION4"],
                 "conjunction", status="live", evidence=["2", "5", "2", " "])   # dup + blank
    assert dg.get(c, "pair").evidence == ("2", "5")          # deduped, blanks dropped, persisted
    assert "evidence: 2, 5" in dg.render(c)


def test_render_lists_the_graph():
    c = _conn()
    dg.init(c, ["ACTION1"])
    md = dg.render(c)
    assert md.startswith("# dagger graph") and "win-game" in md and "ACTION1" in md


def test_confidence_is_the_witness_set_size_killed_is_zero():
    """Graded, idempotent confidence = number of distinct witnessing episodes; never a float. An
    untested dream is 0; a killed node is 0 (definitive counterexample, act on it never)."""
    dream = dg.Node(anchor="d", post="maybe", children=("ACTION1", "ACTION2"), mode="conjunction")
    grounded = dg.Node(anchor="g", post="rigid body", children=("ACTION1",), mode="sequence",
                       status="open", evidence=("0", "1", "7"))
    killed = dg.Node(anchor="k", post="blocked when c9 adjacent", children=("ACTION1",),
                     mode="sequence", status="killed", evidence=("b765", "5695"))
    assert dg.confidence(dream) == 0                          # pure uberty, no witness
    assert dg.confidence(grounded) == 3                       # witnessed×3
    assert dg.confidence(killed) == 0                         # falsified → zero, despite its evidence


def test_actionable_is_a_stakes_threshold_not_a_tier():
    """'Knowledge' is derived: confidence past the stakes-indexed line. The SAME belief is
    actionable for free (a simmer rollout) yet not for a paid commit."""
    dream = dg.Node(anchor="d", post="maybe", children=("ACTION1",), mode="sequence")  # 0 witnesses
    witnessed = dg.Node(anchor="w", post="moves 5", children=("ACTION1",), mode="sequence",
                        status="open", evidence=("0",))                                  # 1 witness
    killed = dg.Node(anchor="k", post="no", children=("ACTION1",), mode="sequence",
                     status="killed", evidence=("0", "1"))

    assert dg.actionable(dream, dg.FREE)                      # imagination acts on an untested guess
    assert not dg.actionable(dream, dg.PAID)                  # but won't spend real budget on it
    assert dg.actionable(witnessed, dg.PAID)                  # one witness clears a paid action
    assert not dg.actionable(witnessed, dg.COMMITTED)         # ...but not a long committed route
    assert not dg.actionable(killed, dg.FREE)                 # killed is never actionable, any stakes
