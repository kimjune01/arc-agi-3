"""Perception unit tests: rendering, deltas, and the stateful observer."""

import numpy as np

from arc_agi_3.perception import Perception, diff_grids, render_grid
from arc_agi_3.structs import FrameData, GameState


def _frame(grid, actions=(1, 2, 3, 4)):
    return FrameData.from_json({
        "game_id": "t", "guid": "g", "state": GameState.NOT_FINISHED.value,
        "frame": [grid], "levels_completed": 0, "win_levels": 7,
        "available_actions": list(actions),
    })


def test_render_blank_and_hex():
    out = render_grid([[0, 1], [10, 15]])
    assert out == ".1\na f".replace(" ", "")  # ".1" / "af"
    assert render_grid([[0, 1], [10, 15]]).splitlines() == [".1", "af"]


def test_diff_localizes_change():
    a = np.zeros((4, 4), dtype=np.int16)
    b = a.copy()
    b[2, 3] = 5
    d = diff_grids(a, b)
    assert d.changed == 1
    assert d.cells == [(2, 3, 0, 5)]
    assert d.bbox == (2, 3, 2, 3)
    assert "(2,3) 0->5" in d.describe()


def test_perception_first_frame_has_no_delta_then_tracks():
    p = Perception()
    o1 = p.observe(_frame([[0, 0], [0, 0]]))
    assert o1.delta is None
    o2 = p.observe(_frame([[0, 1], [0, 0]]))
    assert o2.delta is not None and o2.delta.changed == 1
    assert o2.step == 1
    assert "available actions: ACTION1, ACTION2" in o2.to_prompt(include_grid=False)


def test_palette_counts():
    p = Perception()
    o = p.observe(_frame([[0, 0, 3], [3, 3, 0]]))
    assert o.palette == {0: 3, 3: 3}
