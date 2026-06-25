"""Parser robustness for the LLM agent — no network, no claude calls."""

import numpy as np

from arc_agi_3.agents.llm_agent import LLMAgent
from arc_agi_3.structs import FrameData, GameAction, GameState


def _frame(actions=(1, 2, 3, 4, 6)):
    return FrameData.from_json({
        "game_id": "t", "guid": "g", "state": GameState.NOT_FINISHED.value,
        "frame": [[[0, 0], [0, 0]]], "levels_completed": 0, "win_levels": 7,
        "available_actions": list(actions),
    })


def _agent():
    return LLMAgent(client=None, max_actions=10, seed=1)


def test_parses_clean_json_and_records_note():
    a = _agent()
    act = a._parse('{"action": "ACTION2", "x": null, "y": null, "note": "A2=down"}', _frame())
    assert act.kind is GameAction.ACTION2
    assert a._notes == ["A2=down"]


def test_parses_json_embedded_in_prose():
    a = _agent()
    act = a._parse('Sure: {"action":"ACTION1","note":"go right"} done.', _frame())
    assert act.kind is GameAction.ACTION1


def test_action6_requires_valid_coords():
    a = _agent()
    ok = a._parse('{"action":"ACTION6","x":12,"y":34,"note":"click"}', _frame())
    assert ok.kind is GameAction.ACTION6 and (ok.x, ok.y) == (12, 34)
    # missing coords -> fallback to some available action, never a bad ACTION6
    bad = a._parse('{"action":"ACTION6","x":null,"y":null}', _frame())
    assert not (bad.kind is GameAction.ACTION6 and bad.x is None)


def test_unavailable_action_falls_back():
    a = _agent()
    # ACTION5 not in available -> must fall back to an available one
    act = a._parse('{"action":"ACTION5"}', _frame(actions=(1, 2)))
    assert act.kind in (GameAction.ACTION1, GameAction.ACTION2)


def test_garbage_falls_back():
    a = _agent()
    act = a._parse("no json here at all", _frame())
    assert act.kind in _frame().available_actions
