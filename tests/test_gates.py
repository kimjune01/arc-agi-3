"""Gate contracts: the three exits (hold / bounce / crash), and that the act/commit
path is actually ROUTED through them (shipping a check that no caller hits moves
nothing — the pokayoke lesson).

A bounce is a KNOWN violation -> typed UsageError, fired pre-API (zero budget). A crash
is the UNANTICIPATED -> a non-UsageError exception that propagates uncaught.
"""

import pytest

from arc_agi_3.arcg import gates
from arc_agi_3.arcg import layer0_protocol as l0
from arc_agi_3.arcg.gates import UsageError
from arc_agi_3.structs import FrameData, GameAction, GameState


class FakeClient:
    """Minimal offline game: counts act() calls (the budget meter) so a pregate bounce
    can be shown to cost zero budget."""

    def __init__(self):
        self.calls = 0

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def close(self): pass
    def import_cookies(self, c): pass
    def export_cookies(self): return []
    def list_games(self): return [{"game_id": "fake-1", "title": "FAKE"}]
    def open_scorecard(self, **k): return "card-1"

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


# --- dagger-gate: the action names a live plan node (dagger:<id>) ---------
def test_dagger_gate_holds_on_wellformed_ref():
    assert gates.dagger_gate("dagger:n1") == "dagger:n1"
    assert gates.dagger_gate("  dagger:probe  ") == "dagger:probe"  # normalized


def test_dagger_gate_bounces_on_missing_ref():
    with pytest.raises(UsageError, match="dagger-gate"):
        gates.dagger_gate(None)


def test_dagger_gate_bounces_on_malformed_ref():
    with pytest.raises(UsageError):
        gates.dagger_gate("n1")          # no dagger: prefix
    with pytest.raises(UsageError):
        gates.dagger_gate("dagger:")     # empty id


def test_dagger_gate_crashes_on_nonstr_ref():
    # An unmodeled shape is NOT a known violation -> crash, not bounce.
    with pytest.raises(TypeError):
        gates.dagger_gate(5)


def test_dagger_gate_routed_bounce_costs_zero_budget(game):
    # A malformed action never reaches the API: the pregate fires pre-API.
    l0.start("fake")
    assert game.calls == 0
    with pytest.raises(UsageError):
        l0.act("ACTION1", dagger=None, arbor="arbor:#probe")
    assert game.calls == 0  # zero budget — the API was never called


def test_dagger_gate_routed_hold_reaches_api(game):
    l0.start("fake")
    l0.act("ACTION1", dagger="dagger:probe", arbor="arbor:#probe")
    assert game.calls == 1


# --- arbor-gate: the action names a live hypothesis (arbor:#<id>) ---------
def test_arbor_gate_holds_and_bounces():
    assert gates.arbor_gate("arbor:#4") == "arbor:#4"
    with pytest.raises(UsageError):
        gates.arbor_gate(None)
    with pytest.raises(UsageError):
        gates.arbor_gate("4")          # no arbor:# prefix


def test_arbor_gate_routed_bounce_costs_zero_budget(game):
    l0.start("fake")
    with pytest.raises(UsageError):
        l0.act("ACTION1", dagger="dagger:probe", arbor=None)
    assert game.calls == 0


# --- jotter-gate: a plan vetted vs grounded effects (routing deferred) -----
def test_jotter_gate_holds_and_bounces():
    effects = {"ACTION1": {}, "ACTION3": {}}
    assert gates.jotter_gate(["ACTION1"], effects) == ["ACTION1"]
    with pytest.raises(UsageError, match="ungrounded"):
        gates.jotter_gate(["ACTION2"], effects)  # never demonstrated


# --- postgate: piper ⊕ simmer -> witness / kill ---------------------------
def test_postgate_witness_and_kill():
    assert gates.postgate([[1]], [[1]])["verdict"] == "witness"
    assert gates.postgate([[1]], [[2]])["verdict"] == "kill"


def test_postgate_routed_only_when_prediction_exists(game, monkeypatch):
    calls = []
    monkeypatch.setattr(gates, "postgate", lambda p, r: calls.append((p, r)) or {})
    l0.start("fake")
    l0.act("ACTION1", dagger="dagger:probe", arbor="arbor:#probe")          # no pred
    assert calls == []                                                      # skipped
    l0.act("ACTION1", dagger="dagger:probe", arbor="arbor:#probe", pred=[[9]])
    assert len(calls) == 1                                                  # fired
