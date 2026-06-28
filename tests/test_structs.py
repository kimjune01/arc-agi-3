"""Protocol-conformance tests for FrameData parsing (verified against the
ARC-AGI-3 OpenAPI spec, docs.arcprize.org/arc3v1.yaml — FrameResponse schema)."""

from arc_agi_3.structs import FrameData, GameState


def test_parses_not_started_state():
    """The spec's state enum includes NOT_STARTED (run ended, awaiting RESET).
    GameState must round-trip it rather than raise."""
    f = FrameData.from_json({"game_id": "g", "guid": "x", "state": "NOT_STARTED"})
    assert f.state is GameState.NOT_STARTED


def test_not_started_is_terminal():
    """NOT_STARTED is post-terminal (the run is over); a driver must stop on it."""
    f = FrameData.from_json({"game_id": "g", "guid": "x", "state": "NOT_STARTED"})
    assert f.is_terminal


def test_score_is_levels_completed_and_target_is_win_levels():
    """The live frame carries no `score`; the in-session progress signal is
    levels_completed, the target is win_levels (read, never hard-coded)."""
    f = FrameData.from_json({
        "game_id": "g", "guid": "x", "state": "NOT_FINISHED",
        "levels_completed": 3, "win_levels": 7,
    })
    assert (f.score, f.win_score) == (3, 7)


def test_grid_is_the_settled_frame_not_the_first():
    """`frame` is consecutive animation frames; the settled state is the LAST.
    grid must return frame[-1], not an intermediate animation step."""
    settling = [[[1]], [[2]], [[9]]]  # animates 1 -> 2 -> 9; settled = 9
    f = FrameData.from_json({"game_id": "g", "guid": "x",
                             "state": "NOT_FINISHED", "frame": settling})
    assert f.grid == [[9]]
