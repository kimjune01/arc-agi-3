"""CLI: run a baseline agent against ARC-AGI-3 dev games and print verdicts.

    uv run arc3 --list                       # discover game_ids
    uv run arc3 --agent random --game ls20   # play first game matching "ls20"
    uv run arc3 --agent random --all         # play every game once
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from .client import ArcClient
from .agents.random_agent import RandomAgent
from .agents.llm_agent import LLMAgent

AGENTS = {"random": RandomAgent, "claude": LLMAgent}


def _resolve_games(client: ArcClient, *, game: str | None, run_all: bool) -> list[dict]:
    games = client.list_games()
    if run_all:
        return games
    if game:
        matches = [g for g in games if game.lower() in g["game_id"].lower()
                   or game.lower() in g.get("title", "").lower()]
        if not matches:
            sys.exit(f"No game matches {game!r}. Try --list. Available: "
                     + ", ".join(g["game_id"] for g in games))
        return matches[:1]
    return games[:1]


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(prog="arc3", description="Play ARC-AGI-3 dev games.")
    p.add_argument("--agent", default="random", choices=AGENTS, help="agent to run")
    p.add_argument("--game", help="game_id or title substring (default: first game)")
    p.add_argument("--all", action="store_true", help="play every available game")
    p.add_argument("--list", action="store_true", help="list games and exit")
    p.add_argument("--max-actions", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--model", default="sonnet", help="model for the claude agent")
    p.add_argument("--render", action="store_true",
                   help="stream perception (delta + grid) each step")
    p.add_argument("--render-every", type=int, default=1, help="render every N steps")
    args = p.parse_args()

    with ArcClient() as client:
        if args.list:
            for g in client.list_games():
                print(f"{g['game_id']:24}  {g.get('title', '')}")
            return

        games = _resolve_games(client, game=args.game, run_all=args.all)
        card_id = client.open_scorecard(source_url="https://github.com/kimjune01/arc-agi-3",
                                        tags=[args.agent, "baseline"])
        print(f"scorecard: {card_id}")
        on_observe = None
        if args.render:
            def on_observe(obs):
                if obs.step % args.render_every:
                    return
                grid = obs.step % (args.render_every * 5) == 0  # full grid occasionally
                print("\n" + obs.to_prompt(include_grid=grid))

        kwargs = {"max_actions": args.max_actions, "on_observe": on_observe}
        if args.agent == "claude":
            kwargs["model"] = args.model
        try:
            agent = AGENTS[args.agent](client, **kwargs)
            if hasattr(agent, "_rng"):
                agent._rng.seed(args.seed)
            for g in games:
                verdict = agent.play(game_id=g["game_id"], card_id=card_id)
                print(verdict)
        finally:
            summary = client.close_scorecard(card_id)
            print(f"\nscorecard closed. aggregate score: {summary.get('score')}")
            print(f"view: https://arcprize.org/scorecards/{card_id}")


if __name__ == "__main__":
    main()
