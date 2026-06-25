"""Layer 0 — raw protocol. Faithful wrappers over the REST verbs.

The ONLY module that imports the ArcClient. Speaks ACTION-numbers and raw frames;
does no rendering (that is Layer 1). Hides plumbing — scorecard, guid, cookies —
so nothing above ever sees them. Writes each frame to the substrate and meters
the action budget.
"""

from __future__ import annotations

from ..client import ArcClient
from ..session import Session
from ..structs import Action, FrameData, GameAction
from . import store


class BudgetExceeded(RuntimeError):
    """Raised when an action would exceed the session's tight budget cap."""


def _client(sess: Session | None) -> ArcClient:
    c = ArcClient()
    if sess is not None:
        c.import_cookies(sess.cookies)
    return c


def _apply(sess: Session, frame: FrameData, client: ArcClient, *,
           token: str | None = None, full_reset: bool = False) -> None:
    """Fold a fresh frame into the session: history, budget, grid, cache."""
    if full_reset:
        sess.history = []
        sess.resets += 1
    if token is not None:
        sess.history.append(token)
        sess.actions_spent += 1
    sess.guid = frame.guid
    sess.state = frame.state.value
    sess.score = frame.score
    sess.win_score = frame.win_score
    sess.available_actions = [a.name for a in frame.available_actions]
    sess.prev_grid = sess.grid
    sess.grid = [[int(v) for v in row] for row in frame.grid]
    sess.cookies = client.export_cookies()
    store.cache_put(sess.game_id, sess.history, store.frame_dict(
        sess.grid, sess.state, sess.score, sess.win_score, sess.available_actions))
    sess.save()


# --- raw verbs -----------------------------------------------------------
def games() -> str:
    with _client(None) as c:
        return "\n".join(f"{g['game_id']:24}  {g.get('title', '')}"
                         for g in c.list_games())


def start(game: str, *, tags: str | None = None, budget_cap: int | None = None) -> str:
    with _client(None) as c:
        matches = [g for g in c.list_games()
                   if game.lower() in g["game_id"].lower()
                   or game.lower() in g.get("title", "").lower()]
        if not matches:
            raise SystemExit(f"No game matches {game!r}. Try `arcg games`.")
        g = matches[0]
        card_id = c.open_scorecard(
            source_url="https://github.com/kimjune01/arc-agi-3",
            tags=(tags.split(",") if tags else ["agent"]))
        frame = c.reset(game_id=g["game_id"], card_id=card_id)
        sess = Session(game_id=g["game_id"], card_id=card_id, budget_cap=budget_cap)
        _apply(sess, frame, c, full_reset=True)
    cap = f", budget cap {budget_cap}" if budget_cap else ""
    return (f"started {g['game_id']}  scorecard {card_id}{cap}\n"
            f"state {sess.state}  score {sess.score}/{sess.win_score}  "
            f"raw available {sess.available_actions}\n"
            f"(use `arcg look` to see the board)")


def act(token: str, *, x: int | None = None, y: int | None = None,
        reasoning: str = "") -> FrameData:
    """Raw ACTION1..7 (escape hatch). Returns the new FrameData. Meters budget."""
    sess = store.load()
    try:
        kind = GameAction[token.upper()]
    except KeyError as e:
        raise SystemExit(f"Unknown action {token!r}. Use ACTION1..7 or RESET.") from e
    if sess.budget_cap is not None and sess.actions_spent >= sess.budget_cap:
        raise BudgetExceeded(
            f"budget cap {sess.budget_cap} reached ({sess.actions_spent} spent); terminating.")
    if kind.is_complex and (x is None or y is None):
        raise SystemExit("ACTION6 requires x and y (0-63).")
    action = Action(kind, x=x, y=y, reasoning=reasoning)
    with _client(sess) as c:
        frame = c.act(action, game_id=sess.game_id, guid=sess.guid, card_id=sess.card_id)
        _apply(sess, frame, c, token=_token_str(kind, x, y))
    return frame


def reset(*, full: bool = True) -> FrameData:
    """RESET. Full reset clears history (the deterministic anchor)."""
    sess = store.load()
    with _client(sess) as c:
        frame = c.reset(game_id=sess.game_id, card_id=sess.card_id,
                        guid=None if full else sess.guid)
        _apply(sess, frame, c, full_reset=full)
    return frame


def end() -> str:
    sess = store.load_or_none()
    if sess is None:
        return "no active session."
    with _client(sess) as c:
        summary = c.close_scorecard(sess.card_id)
    out = (f"closed scorecard {sess.card_id} | aggregate score {summary.get('score')}\n"
           f"actions spent {sess.actions_spent} | resets {sess.resets}\n"
           f"view: https://arcprize.org/scorecards/{sess.card_id}")
    Session.clear()
    return out


def _token_str(kind: GameAction, x: int | None, y: int | None) -> str:
    return f"{kind.name}:{x},{y}" if kind.is_complex else kind.name
