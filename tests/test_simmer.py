"""simmer engine + differential-test harness."""

import json

import numpy as np

from arc_agi_3.simmer import cli
from arc_agi_3.simmer.engine import step


def _scene():
    # 12x6 corridor (3); avatar (12) at rows 6-7 cols 2-3, 9-tail directly below at 8-9.
    g = np.full((12, 6), 3, np.int16)
    g[6:8, 2:4] = 12
    g[8:10, 2:4] = 9
    return g


def test_step_slides_avatar_and_tail_up():
    after = step(_scene(), "ACTION1")  # up by STEP=5
    assert (after[1:3, 2:4] == 12).all()     # avatar moved rows 6-7 -> 1-2
    assert (after[3:5, 2:4] == 9).all()      # tail followed rows 8-9 -> 3-4
    assert (after[6:10, 2:4] == 3).all()     # vacated cells become corridor


def test_step_blocked_at_boundary_is_noop():
    g = _scene()
    # avatar already near the top: moving up 5 would leave the grid -> no move
    g = np.full((6, 6), 3, np.int16)
    g[2:4, 2:4] = 12
    out = step(g, "ACTION1")
    assert np.array_equal(out, g)  # blocked, identity


def test_unknown_action_is_identity():
    g = _scene()
    assert np.array_equal(step(g, "ACTION5"), g)


def test_test_harness_counts_reproduced(tmp_path):
    before = _scene()
    after = step(before, "ACTION1")
    wrong = before.copy()  # a transition the engine will NOT reproduce
    corpus = tmp_path / "transitions.jsonl"
    corpus.write_text(
        json.dumps({"action": "ACTION1", "before": before.tolist(), "after": after.tolist()}) + "\n"
        + json.dumps({"action": "ACTION1", "before": before.tolist(), "after": wrong.tolist()}) + "\n"
    )
    report = cli.test(corpus)
    assert "1/2 transitions reproduced" in report
    assert "[0] ACTION1" in report and "✓" in report
    assert "✗" in report
