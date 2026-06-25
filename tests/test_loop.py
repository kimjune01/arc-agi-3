"""Offline proof that the play loop produces a verdict.

No network: a fake client feeds canned frames ending in GAME_OVER, and we
assert the RandomAgent returns a FAIL verdict. This locks the loop/verdict
logic independent of having an ARC_API_KEY.
"""

from arc_agi_3.agents.random_agent import RandomAgent
from arc_agi_3.structs import FrameData, GameState


def _frame(state, score=0, actions=(1, 2, 3, 4)):
    return FrameData.from_json({
        "game_id": "test-0000",
        "guid": "guid-1",
        "state": state.value,
        "frame": [[[0, 0], [0, 0]]],
        "levels_completed": score,
        "win_levels": 10,
        "available_actions": list(actions),
    })


class FakeClient:
    """Returns NOT_FINISHED for a few steps, then GAME_OVER (a loss)."""

    def __init__(self, lose_after=5):
        self.lose_after = lose_after
        self.calls = 0

    def reset(self, **_):
        return _frame(GameState.NOT_FINISHED)

    def act(self, action, **_):
        self.calls += 1
        state = GameState.GAME_OVER if self.calls >= self.lose_after else GameState.NOT_FINISHED
        return _frame(state, score=0)


def test_random_agent_loses():
    agent = RandomAgent(FakeClient(lose_after=5), max_actions=200, seed=0)
    verdict = agent.play(game_id="test-0000", card_id="card-1")
    assert not verdict.won
    assert verdict.state is GameState.GAME_OVER
    assert verdict.actions_taken == 5
    assert "FAIL" in str(verdict)


def test_available_actions_parse_ints():
    f = _frame(GameState.NOT_FINISHED, actions=(1, 2, 6))
    names = [a.name for a in f.available_actions]
    assert names == ["ACTION1", "ACTION2", "ACTION6"]
