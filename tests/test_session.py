"""Session persistence round-trip (no network)."""

from arc_agi_3.session import Session


def test_round_trip(tmp_path):
    f = tmp_path / "session.json"
    s = Session(game_id="ls20-x", guid="g1", card_id="c1", score=2, win_score=7,
                step=4, available_actions=["ACTION1", "ACTION2"],
                grid=[[0, 1], [2, 3]],
                cookies=[{"name": "GAMESESSION", "value": "v", "domain": "d", "path": "/"}],
                notes=["avatar=12"])
    s.save(f)
    loaded = Session.load(f)
    assert loaded == s
    assert loaded.cookies[0]["name"] == "GAMESESSION"


def test_load_or_none(tmp_path):
    f = tmp_path / "missing.json"
    assert Session.load_or_none(f) is None
    Session(game_id="g").save(f)
    assert Session.load_or_none(f).game_id == "g"


def test_clear(tmp_path):
    f = tmp_path / "session.json"
    Session(game_id="g").save(f)
    Session.clear(f)
    assert not f.exists()
    Session.clear(f)  # idempotent
