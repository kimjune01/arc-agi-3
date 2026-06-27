"""The reasoner agent: Claude Code drives the tools, one experiment unit per session.

This is the "Claude Code = reasoner" model (PLAN.md): instead of a one-shot mega-prompt, a fresh
agentic `claude` session is given FREEDOM to call the project CLIs (arcg/jotter/simmer) and run
ONE unit of experiment, then stop. The outer harness manages the game lifecycle and re-spawns a
fresh session per unit.

Why per-unit + stop: context is bounded and REFRESHED each unit. The memory (jotter's corpus,
arcg notes) persists on disk, so a fresh session re-hydrates from it (the "memory is a cache"
design — the persistent stores and `render` exist precisely so context can be thrown away and
rebuilt). One clean hypothesis tested and recorded = one unit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..arcg import layer0_protocol as l0
from ..arcg import store

PROJECT_ROOT = Path(__file__).resolve().parents[3]   # .../src/arc_agi_3/agents/ -> repo root
_TERMINAL = ("WIN", "GAME_OVER")

# The CLIs the agentic session may call (free inspection + the budget-bearing intent verbs), plus
# read/append to the DURABLE findings file (survives the session, so context refreshes across runs).
_ALLOWED = ["Bash(uv run arcg:*)", "Bash(uv run jotter:*)",
            "Bash(uv run simmer:*)", "Bash(uv run dagger:*)",
            "Bash(cat .arc/findings.md:*)", "Bash(echo:*)"]

UNIT_TASK = """You are the reasoner for an agent playing ARC-AGI-3, an unknown 64x64 grid game. \
A game is ALREADY IN PROGRESS with a tight action budget: every act is costly, inspection is free. \
You are a FRESH session with no memory of prior turns — the memory lives on disk, so re-hydrate first.

Toolbox (all via `uv run <tool> ...`, run from the repo root):
  arcg look | objects | diff            perceive (objects = connected components; isolates the avatar)
  arcg move <up|down|left|right> | interact | click <x> <y>   ACT (spends one budget unit each)
  arcg note "<finding>" | notes         your durable scratchpad across sessions
  jotter stats | effects | log | trace  read the grounded record (FREE). `effects` names the
                                        move-counter and other resource facts straight from history.
  simmer ...                            predict an action's result for FREE before spending a real one
  dagger render | plan <goal> | decompose <anchor> <goal> <child>...   the PLAN graph (FREE). Record
                                        your decomposition of the goal into 2+ subgoals; reuse a
                                        subgoal's anchor instead of renaming it.

GOAL: raise the score (levels_completed) toward state WIN.

Your durable findings live in `.arc/findings.md` (survives this session; the session itself does
NOT, so that file plus jotter's corpus IS your memory).

Do exactly ONE UNIT OF EXPERIMENT, then STOP. Do not try to win in one session.
  1. Re-hydrate: `cat .arc/findings.md`, `jotter stats`, `jotter effects`, `arcg look`, `arcg objects`.
  2. Form ONE specific question you're unsure of (e.g. "which object is the avatar? does ACTION3
     move it left?") or pick the next subgoal toward WIN.
  3. Test it with the FEWEST real actions. Predict with simmer first when it saves a move. Watch the
     delta / objects to read the result. The move-counter changes every action — discount it; look
     for what ELSE moved.
  4. Record the finding durably (one line): `echo "<what you learned>" >> .arc/findings.md`. Then
     END YOUR TURN.

Do NOT run `arcg start` or `arcg end` — the harness owns the game lifecycle. One hypothesis tested
and recorded is a complete unit. Keep it small so the next session can refresh cleanly."""


def run_unit(*, model: str = "sonnet", max_turns: int = 40, timeout: float = 420.0) -> dict:
    """Run ONE experiment unit as a fresh agentic claude session. Returns the parsed result dict
    (the session's `result` text plus its cost/turns). Context is fresh; the memory persists."""
    cmd = [
        "claude", "-p", UNIT_TASK,
        "--output-format", "json",
        "--model", model,
        "--max-turns", str(max_turns),
        "--allowedTools", *_ALLOWED,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, cwd=PROJECT_ROOT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "result": f"(unit timed out after {timeout}s)"}
    if proc.returncode != 0:
        return {"ok": False, "result": f"claude exited {proc.returncode}: {proc.stderr[:300]}"}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "result": proc.stdout[:300]}
    return {"ok": not data.get("is_error"), "result": (data.get("result") or "").strip(),
            "turns": data.get("num_turns"), "cost_usd": data.get("total_cost_usd")}


def run(game: str, *, units: int = 5, budget: int = 20, model: str = "sonnet") -> list[dict]:
    """Drive `game` as a sequence of fresh per-unit agentic sessions. The harness starts/ends the
    game and stops early on WIN/GAME_OVER or budget exhaustion; each unit refreshes context."""
    l0.start(game, budget_cap=budget)
    units_log: list[dict] = []
    try:
        for i in range(units):
            sess = store.load_or_none()
            if sess and (sess.state in _TERMINAL
                         or (sess.budget_cap is not None and sess.actions_spent >= sess.budget_cap)):
                break
            r = run_unit(model=model)
            sess = store.load_or_none()
            r["unit"] = i + 1
            r["score"] = sess.score if sess else None
            r["spent"] = sess.actions_spent if sess else None
            r["state"] = sess.state if sess else None
            units_log.append(r)
    finally:
        l0.end()
    return units_log


def main() -> None:
    import argparse

    from dotenv import load_dotenv

    load_dotenv()
    p = argparse.ArgumentParser(prog="reason", description="Drive a game as per-unit agentic sessions.")
    p.add_argument("game", help="game_id or substring")
    p.add_argument("--units", type=int, default=5, help="experiment units (fresh sessions)")
    p.add_argument("--budget", type=int, default=20, help="action cap for the whole run")
    p.add_argument("--model", default="sonnet")
    args = p.parse_args()
    for r in run(args.game, units=args.units, budget=args.budget, model=args.model):
        head = f"--- unit {r['unit']} | score {r['score']} | spent {r['spent']} | {r['state']}"
        if r.get("turns"):
            head += f" | {r['turns']} turns ${r.get('cost_usd', 0):.3f}"
        print(head + " ---")
        print((r.get("result") or "").strip()[:600])


if __name__ == "__main__":
    main()
