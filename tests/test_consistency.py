"""Consistency suite: history, budget meter/cap, cache round-trip, and the
determinism verdict — offline, against a deterministic fake game (and a
nondeterministic one to prove the verdict fires).

The fake's frame is a pure function of the action sequence since RESET, so
restore-replay must reproduce it: that is exactly the property Layer 2 measures.
"""

import pytest

from arc_agi_3.arcg import layer0_protocol as l0
from arc_agi_3.arcg import layer1_intent as l1
from arc_agi_3.arcg import layer2_state as l2
from arc_agi_3.structs import FrameData, GameAction, GameState


def _frame(seq, *, extra=0):
    n = len(seq)
    ssum = sum(GameAction[t.split(":")[0]].value for t in seq)
    grid = [[(n + extra) % 16, ssum % 16], [(n * 2) % 16, 0]]
    return FrameData(game_id="fake-1", guid="guid-1", state=GameState.NOT_FINISHED,
                     frame=[grid], score=0, win_score=10,
                     available_actions=[GameAction(i) for i in (1, 2, 3, 4, 5, 6, 7)])


class FakeClient:
    deterministic = True

    def __init__(self):
        self.seq = []
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def import_cookies(self, c):
        pass

    def export_cookies(self):
        return []

    def list_games(self):
        return [{"game_id": "fake-1", "title": "FAKE"}]

    def open_scorecard(self, **k):
        return "card-1"

    def close_scorecard(self, card_id):
        return {"score": 0}

    def reset(self, *, game_id, card_id, guid=None):
        if guid is None:
            self.seq = []
        return _frame(self.seq)

    def act(self, action, *, game_id, guid, card_id):
        self.calls += 1
        tok = (f"{action.kind.name}:{action.x},{action.y}"
               if action.kind.is_complex else action.kind.name)
        self.seq.append(tok)
        extra = 0 if self.deterministic else self.calls
        return _frame(self.seq, extra=extra)


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = FakeClient()
    monkeypatch.setattr(l0, "_client", lambda sess=None: fake)
    return fake


def test_history_and_budget(game):
    l0.start("fake")
    l1.move("left")
    l1.move("left")
    out = l2.history()
    assert "2 actions since RESET" in out
    assert "ACTION3 ACTION3" in out


def test_budget_cap_terminates(game):
    l0.start("fake", budget_cap=2)
    l1.move("left")
    l1.move("right")
    with pytest.raises(l0.BudgetExceeded):
        l1.move("up")


def test_cache_round_trip_same_sequence(game):
    from arc_agi_3.arcg import store
    l0.start("fake")
    l1.move("left")
    l1.move("up")
    cached = store.cache_get("fake-1", ["ACTION3", "ACTION1"])
    assert cached is not None
    assert cached["grid"] == store.load().grid  # cache matches live frame


def test_snapshot_restore_deterministic(game):
    l0.start("fake")
    l1.move("left")
    l1.move("left")
    l2.snapshot("base")
    l1.move("right")  # diverge
    out = l2.restore("base")
    assert "DETERMINISTIC ✓" in out
    from arc_agi_3.arcg import store
    assert store.load().history == ["ACTION3", "ACTION3"]


def test_peek_is_free(game):
    l0.start("fake")
    l1.move("left")
    l2.snapshot("s")
    from arc_agi_3.arcg import store
    spent_before = store.load().actions_spent
    out = l2.peek("s")
    assert "grid" in out
    assert store.load().actions_spent == spent_before  # no budget spent


def test_nondeterminism_detected(game):
    game.deterministic = False
    l0.start("fake")
    l1.move("left")
    l1.move("left")
    l2.snapshot("base")
    out = l2.restore("base")
    assert "NON-DETERMINISTIC ✗" in out
    assert "FINDING" in out
