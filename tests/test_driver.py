"""driver serial loop — offline sanity against a deterministic fake game.

Proves the loop closes through the GATED path (acts, records, reconciles) without the real API,
and that `run`/`decide` are importable (the shared surface the CLI also calls). The cognitive
steps (arbor abduce/witness, dagger decompose) are deferred and not asserted.
"""

import pytest

from arc_agi_3 import driver
from arc_agi_3.arcg import layer0_protocol as l0
from arc_agi_3.arcg import store
from arc_agi_3.jotter import db
from arc_agi_3.structs import FrameData, GameAction, GameState


class FakeClient:
    """Minimal offline game: a fixed frame, counts act() calls (the budget meter)."""

    def __init__(self):
        self.calls = 0

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def close(self): pass
    def import_cookies(self, c): pass
    def export_cookies(self): return []
    def list_games(self): return [{"game_id": "fake-1", "title": "FAKE"}]
    def open_scorecard(self, **k): return "card-1"
    def close_scorecard(self, card_id): return {"score": 0}

    def _frame(self):
        return FrameData(game_id="fake-1", guid="g", state=GameState.NOT_FINISHED,
                         frame=[[[0, 0], [0, 0]]], score=0, win_score=10,
                         available_actions=[GameAction(i) for i in range(1, 8)])

    def reset(self, **k): return self._frame()

    def act(self, action, **k):
        self.calls += 1
        return self._frame()


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = FakeClient()
    monkeypatch.setattr(l0, "_client", lambda sess=None: fake)
    return fake


def test_run_drives_through_the_gated_path(game):
    conn = db.connect(":memory:")
    result = driver.run("fake", budget=4, conn=conn)
    s = result["summary"]
    assert s["steps"] == 4 and s["spent"] == 4        # spent the budget through the gates
    assert game.calls == 4                             # every step reached the (fake) API
    assert len(result["log"]) == 4
    # init seeded the dagger graph with real leaves + the apex (now with the pre-baked spine)
    assert db.get(conn, "win-game") is not None
    assert db.get(conn, "ACTION1") is not None
    # the apex spine is pre-baked (plan HITS it), but the per-level BODY isn't witnessed, so the
    # driver never exploits — every step is explore (the spend that earns witnesses).
    assert all(e["mode"] == "explore" for e in result["log"])


def test_decide_returns_a_real_available_action(game):
    l0.start("fake")
    sess = store.load()
    action, info = driver.decide(sess, counts={})
    assert action in sess.available_actions            # the shared surface, importable
    assert info["mode"] == "explore"                   # no plan, no conn → the exploration floor


def test_decide_exploits_a_goal_plan_witnessed_enough_to_commit(game):
    """The pragmatist gate, wired: a win-recipe witnessed ×2 clears COMMITTED stakes, so the driver
    follows it (exploit) instead of exploring — and resolves its primitive next action."""
    from arc_agi_3 import dagger as dg
    l0.start("fake")
    sess = store.load()
    conn = db.connect(":memory:")
    dg.init(conn, ["ACTION1", "ACTION2", "ACTION3", "ACTION4"])
    # the recipe is the per-level BODY under the pre-baked spine (deposit-one-point), witnessed×2
    dg.decompose(conn, dg.DEPOSIT_ANCHOR, dg.DEPOSIT_POST, ["ACTION1"], "sequence", status="open",
                 evidence=["0", "1"])                  # witnessed×2 → actionable at COMMITTED
    action, info = driver.decide(sess, counts={}, conn=conn, goal=dg.WIN)
    # decide descends the structural apex to the witnessed body and commits IT
    assert info["mode"] == "exploit" and info["node"] == dg.DEPOSIT_ANCHOR
    assert action == "ACTION1"


def test_decide_will_not_commit_an_under_witnessed_plan(game):
    """The same recipe witnessed only ×1 does NOT clear COMMITTED stakes — the driver keeps
    EXPLORING (witnessing) rather than blindly following an under-confident route."""
    from arc_agi_3 import dagger as dg
    l0.start("fake")
    sess = store.load()
    conn = db.connect(":memory:")
    dg.init(conn, ["ACTION1", "ACTION2", "ACTION3", "ACTION4"])
    dg.decompose(conn, dg.DEPOSIT_ANCHOR, dg.DEPOSIT_POST, ["ACTION1"], "sequence", status="open",
                 evidence=["0"])                       # only ×1 < COMMITTED threshold
    action, info = driver.decide(sess, counts={}, conn=conn, goal=dg.WIN)
    assert info["mode"] == "explore"
    assert action in sess.available_actions
