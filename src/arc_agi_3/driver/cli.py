"""drive CLI — a thin wrapper over driver.run (the same function a programmatic policy imports).

    uv run drive ls20 --budget 25            # drive a game through the gated loop
    uv run drive ls20 --budget 25 --goal "win game" --max-steps 20
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from .loop import run


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(prog="drive", description="Drive a game through the gated serial loop.")
    p.add_argument("game", help="game_id or substring")
    p.add_argument("--budget", type=int, default=25, help="action cap (the only paid spend)")
    p.add_argument("--goal", default="win game", help="goal predicate to plan toward")
    p.add_argument("--max-steps", type=int, default=None, help="stop after N steps (besides budget)")
    args = p.parse_args()

    result = run(args.game, goal=args.goal, budget=args.budget, max_steps=args.max_steps)
    for e in result["log"]:
        print(f"{e['step']:3} {e['action']:8} plan={e['plan']:5} sim_move={int(e['sim_move'])} "
              f"surprise={int(e['surprise'])} score={e['score']} spent={e['spent']}")
    s = result["summary"]
    print(f"--- {s['steps']} steps | {s['spent']} spent | score {s['score']} | "
          f"{s['surprises']} surprises | {s['state']}")


if __name__ == "__main__":
    main()
