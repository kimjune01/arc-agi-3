"""`arcg` — agent-facing CLI tools for playing one ARC-AGI-3 game.

Each command is a separate process that loads/saves the persisted Session
(.arc/session.json), so an agent with a shell (e.g. Claude Code) can play by
calling these commands and reading their stdout. Session affinity cookies and
the current grid are persisted between calls.

    arcg games                       list game ids
    arcg start ls20                  open scorecard, reset, show first frame
    arcg look [--no-grid]            re-print the current observation
    arcg act ACTION1                 take a simple action; show delta + frame
    arcg act ACTION6 --x 12 --y 34   take the complex (click) action
    arcg note "12-block = avatar"    jot a memory into the scratchpad
    arcg status                      compact state/score/step + notes
    arcg reset                       reset current level/game
    arcg end                         close the scorecard, clear session
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
from dotenv import load_dotenv

from .client import ArcClient
from .perception import Perception
from .structs import Action, FrameData, GameAction, GameState
from .session import Session


def _client(sess: Session | None = None) -> ArcClient:
    c = ArcClient()
    if sess is not None:
        c.import_cookies(sess.cookies)
    return c


def _observe(sess: Session, *, include_grid: bool = True) -> str:
    """Build an Observation from the stored grid vs the session's prior grid."""
    frame = FrameData(
        game_id=sess.game_id, guid=sess.guid,
        state=GameState(sess.state),
        frame=[sess.grid] if sess.grid else [],
        score=sess.score, win_score=sess.win_score,
        available_actions=[GameAction[a] for a in sess.available_actions],
    )
    return Perception().observe(frame).to_prompt(include_grid=include_grid)


def _persist_frame(sess: Session, frame: FrameData, client: ArcClient) -> str:
    """Update the session from a fresh frame, return a delta+frame report."""
    perc = Perception()
    if sess.grid:
        perc._prev = np.asarray(sess.grid, dtype=np.int16)
        perc.step = sess.step
    obs = perc.observe(frame)
    sess.guid = frame.guid
    sess.state = frame.state.value
    sess.score = frame.score
    sess.win_score = frame.win_score
    sess.step = obs.step + 1
    sess.available_actions = [a.name for a in frame.available_actions]
    sess.grid = [[int(v) for v in row] for row in obs.grid.tolist()]
    sess.cookies = client.export_cookies()
    sess.save()
    return obs.to_prompt(include_grid=True)


# --- commands ------------------------------------------------------------

def cmd_games(args) -> None:
    with _client() as c:
        for g in c.list_games():
            print(f"{g['game_id']:24}  {g.get('title', '')}")


def cmd_start(args) -> None:
    with _client() as c:
        games = c.list_games()
        matches = [g for g in games if args.game.lower() in g["game_id"].lower()
                   or args.game.lower() in g.get("title", "").lower()]
        if not matches:
            sys.exit(f"No game matches {args.game!r}. Try `arcg games`.")
        g = matches[0]
        card_id = c.open_scorecard(
            source_url="https://github.com/kimjune01/arc-agi-3",
            tags=(args.tags.split(",") if args.tags else ["agent"]),
        )
        frame = c.reset(game_id=g["game_id"], card_id=card_id)
        sess = Session(game_id=g["game_id"], card_id=card_id)
        report = _persist_frame(sess, frame, c)
        print(f"started {g['game_id']}  scorecard {card_id}")
        print(report)


def cmd_look(args) -> None:
    sess = Session.load()
    print(_observe(sess, include_grid=not args.no_grid))


def cmd_act(args) -> None:
    sess = Session.load()
    try:
        kind = GameAction[args.action.upper()]
    except KeyError:
        sys.exit(f"Unknown action {args.action!r}. Use ACTION1..7 or RESET.")
    if kind not in [GameAction[a] for a in sess.available_actions] and kind is not GameAction.RESET:
        print(f"warning: {kind.name} not in available {sess.available_actions}", file=sys.stderr)
    if kind.is_complex and (args.x is None or args.y is None):
        sys.exit("ACTION6 requires --x and --y (0-63).")
    action = Action(kind, x=args.x, y=args.y, reasoning=args.note or "")
    with _client(sess) as c:
        frame = c.act(action, game_id=sess.game_id, guid=sess.guid, card_id=sess.card_id)
        print(_persist_frame(sess, frame, c))
        if frame.is_terminal:
            print(f"\nTERMINAL: {frame.state.value}. `arcg end` to close the scorecard.")


def cmd_note(args) -> None:
    sess = Session.load()
    sess.notes.append(args.text)
    sess.save()
    print(f"noted ({len(sess.notes)} total)")


def cmd_status(args) -> None:
    sess = Session.load()
    target = sess.win_score if sess.win_score is not None else "?"
    print(f"game {sess.game_id} | state {sess.state} | score {sess.score}/{target} "
          f"| step {sess.step} | actions {sess.available_actions}")
    if sess.notes:
        print("notes:")
        for n in sess.notes:
            print(f"  - {n}")


def cmd_reset(args) -> None:
    sess = Session.load()
    with _client(sess) as c:
        frame = c.reset(game_id=sess.game_id, card_id=sess.card_id,
                        guid=None if args.full else sess.guid)
        print(_persist_frame(sess, frame, c))


def cmd_end(args) -> None:
    sess = Session.load_or_none()
    if sess is None:
        print("no active session.")
        return
    with _client(sess) as c:
        summary = c.close_scorecard(sess.card_id)
    print(f"closed scorecard {sess.card_id} | aggregate score {summary.get('score')}")
    print(f"view: https://arcprize.org/scorecards/{sess.card_id}")
    Session.clear()


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(prog="arcg", description="ARC-AGI-3 agent tools.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("games", help="list game ids").set_defaults(fn=cmd_games)

    sp = sub.add_parser("start", help="start a game")
    sp.add_argument("game", help="game id or title substring")
    sp.add_argument("--tags", help="comma-separated scorecard tags")
    sp.set_defaults(fn=cmd_start)

    sp = sub.add_parser("look", help="re-print current observation")
    sp.add_argument("--no-grid", action="store_true", help="omit the grid")
    sp.set_defaults(fn=cmd_look)

    sp = sub.add_parser("act", help="take an action")
    sp.add_argument("action", help="ACTION1..7 or RESET")
    sp.add_argument("--x", type=int, help="x for ACTION6 (0-63)")
    sp.add_argument("--y", type=int, help="y for ACTION6 (0-63)")
    sp.add_argument("--note", help="reasoning attached to the action")
    sp.set_defaults(fn=cmd_act)

    sp = sub.add_parser("note", help="append a memory")
    sp.add_argument("text")
    sp.set_defaults(fn=cmd_note)

    sub.add_parser("status", help="compact status + notes").set_defaults(fn=cmd_status)

    sp = sub.add_parser("reset", help="reset level/game")
    sp.add_argument("--full", action="store_true", help="full game reset (drop guid)")
    sp.set_defaults(fn=cmd_reset)

    sub.add_parser("end", help="close scorecard and clear session").set_defaults(fn=cmd_end)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
