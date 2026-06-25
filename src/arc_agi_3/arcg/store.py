"""Substrate shared by all layers: persisted session, the determinism cache, and
named snapshots. Not a layer — holds no game logic and never touches the API.

The cache is keyed by `(game_id, action sequence)` — the bench identity of a
state. It lets higher layers `peek` any visited state for free and lets `restore`
check whether a replay reproduced the cached frame (the determinism measurement).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..session import STATE_DIR, Session

CACHE_FILE = STATE_DIR / "cache.json"
SNAP_DIR = STATE_DIR / "snapshots"


# --- session -------------------------------------------------------------
def load() -> Session:
    return Session.load()


def load_or_none() -> Session | None:
    return Session.load_or_none()


def save(sess: Session) -> None:
    sess.save()


# --- frame -> dict -------------------------------------------------------
def frame_dict(grid, state, score, win_score, available_actions) -> dict:
    return {
        "grid": grid,
        "state": state,
        "score": score,
        "win_score": win_score,
        "available_actions": list(available_actions),
    }


# --- determinism cache ---------------------------------------------------
def _seq_key(game_id: str, history: list[str]) -> str:
    return game_id + "|" + ",".join(history)


def _load_cache() -> dict:
    return json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}


def cache_put(game_id: str, history: list[str], frame: dict) -> None:
    cache = _load_cache()
    cache[_seq_key(game_id, history)] = frame
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache))


def cache_get(game_id: str, history: list[str]) -> dict | None:
    return _load_cache().get(_seq_key(game_id, history))


# --- named snapshots -----------------------------------------------------
def save_snapshot(label: str, game_id: str, history: list[str]) -> None:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    (SNAP_DIR / f"{label}.json").write_text(
        json.dumps({"game_id": game_id, "sequence": history})
    )


def load_snapshot(label: str) -> dict:
    path = SNAP_DIR / f"{label}.json"
    if not path.exists():
        raise FileNotFoundError(f"No snapshot {label!r}. List with `arcg history`.")
    return json.loads(path.read_text())


def list_snapshots() -> list[str]:
    if not SNAP_DIR.exists():
        return []
    return sorted(p.stem for p in SNAP_DIR.glob("*.json"))
