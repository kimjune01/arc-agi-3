"""simmer engine (prior-free) + the differential-test harness.

ARC-AGI-3 forbids problem-specific priors, so the shipped engine is the IDENTITY until mechanics
are learned. These tests pin that, plus the harness that will measure a learned engine later.
"""

import json

import numpy as np

from arc_agi_3.simmer import cli, engine
from arc_agi_3.simmer.engine import MODELED, step


def _scene():
    g = np.full((12, 6), 3, np.int16)
    g[6:8, 2:4] = 12
    g[8:10, 2:4] = 9
    return g


def test_engine_is_prior_free_identity():
    g = _scene()
    for a in ("ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION6", "ACTION7"):
        assert np.array_equal(step(g, a), g)     # no game-specific mechanics: every action a no-op
    assert MODELED == frozenset()                # models nothing yet (learned per game, never assumed)


def test_shipped_engine_has_no_game_specific_mechanics():
    # the LS20 model lives only in the quarantined fixture, never in the shipped engine
    for sym in ("PASSABLE", "AVATAR", "_DELTA", "_slide", "_deplete_bar"):
        assert not hasattr(engine, sym), f"engine leaks game-specific symbol {sym}"


def test_test_harness_counts_reproduced(tmp_path):
    # The identity engine reproduces a no-op transition and misses a changing one.
    g = _scene()
    changed = g.copy()
    changed[0, 0] = 1
    corpus = tmp_path / "transitions.jsonl"
    corpus.write_text(
        json.dumps({"action": "ACTION1", "before": g.tolist(), "after": g.tolist()}) + "\n"
        + json.dumps({"action": "ACTION1", "before": g.tolist(), "after": changed.tolist()}) + "\n"
    )
    report = cli.test(corpus)
    assert "1/2 transitions reproduced" in report
    assert "[0] ACTION1" in report and "✓" in report
    assert "✗" in report   # the changing transition is missed (identity can't model it yet)
