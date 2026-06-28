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
import shutil
from pathlib import Path

from ..arcg import layer0_protocol as l0
from ..arcg import store
from ..session import STATE_DIR

PROJECT_ROOT = Path(__file__).resolve().parents[3]   # .../src/arc_agi_3/agents/ -> repo root
_TERMINAL = ("WIN", "GAME_OVER")

# The durable memories — the agent's actual product. A checkpoint is a copy of these; resuming from
# one is how learning compounds across runs (and how it transfers to another agent/machine).
MEMORY_FILES = ("notes.md", "transitions.jsonl", "graph.db")

# The tool allowlists ENFORCE the read/write split between the two passes (not just the prompt):
#   FORWARD (wake/explore) acts the game and writes jotter + notes; it only READS dagger (the plan
#     the sleep pass built) — render/plan/get, never decompose.
#   BACKWARD (sleep/consolidate) reads everything and WRITES dagger (decompose); it never plays
#     (no `arcg act` — only `arcg note`/`notes`).
_FORWARD_ALLOWED = ["Bash(uv run arcg:*)", "Bash(uv run jotter:*)",
                    "Bash(uv run dagger render:*)", "Bash(uv run dagger plan:*)",
                    "Bash(uv run dagger get:*)"]
_BACKWARD_ALLOWED = ["Bash(uv run arcg note:*)", "Bash(uv run arcg forget:*)",
                     "Bash(uv run jotter:*)", "Bash(uv run dagger:*)"]


def _restore_checkpoint(src: Path) -> int:
    """Copy a checkpoint's durable memories into the live state dir — continue from where a prior
    run (or another agent) left off. Returns how many memory files were restored."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in MEMORY_FILES:
        p = src / f
        if p.exists():
            shutil.copy2(p, STATE_DIR / f)
            n += 1
    return n


def _save_checkpoint(dst: Path) -> None:
    """Snapshot the live durable memories into a checkpoint — the run's actual output, resumable."""
    dst.mkdir(parents=True, exist_ok=True)
    for f in MEMORY_FILES:
        p = STATE_DIR / f
        if p.exists():
            shutil.copy2(p, dst / f)

FORWARD_TASK = """You are the FORWARD (waking) pass of an agent studying ARC-AGI-3, an unknown \
64x64 grid game. You EXPLORE and RECORD; a separate sleep pass later turns your records into \
reusable structure. YOUR GOAL IS TO LEARN AND LEAVE DURABLE MEMORY — not to play or win. The \
product of your turn is a recorded finding the next session inherits, NOT a higher score. Score \
moving is a SIGNAL to learn from ("what did I do that changed it?"), and winning is a SIDE EFFECT \
of understanding the game well enough; neither is the objective. Maximize WHAT YOU LEARN per action.

You know NOTHING about the rules: not what any action does, not whether there is a character, \
movement, or a goal object — some games have no movement at all. Assume nothing; learn ONLY by \
acting and watching what changes. A game is ALREADY IN PROGRESS with a tight action budget (every \
act is costly; inspection is free). You are a FRESH session with no memory — it lives on disk, so \
re-hydrate first.

Toolbox (all via `uv run <tool> ...`, run from the repo root):
  arcg actions                          which ACTION1..7 are available right now (FREE).
  arcg objects | diff                   perceive COMPACTLY: `objects` lists the connected pieces;
                                        `diff` shows just what changed after your last action.
  arcg look                             the full 64x64 grid — AVOID it (each dump bloats context and
                                        slows every later turn; repeating it is what times a unit out).
                                        At most ONCE, only if objects+diff can't answer your question.
  arcg act ACTIONn [--x N --y N]        ACT (spends one budget unit). You don't know what any action
                                        does — discover it. Some actions take a coordinate; most don't.
  arcg note "<finding>" | notes         your DURABLE memory across sessions (survives the session).
  jotter stats | effects | diff | trace read the grounded record (FREE). `effects` = per-action COUNT
                                        facts (e.g. something that changes every step no matter what you
                                        do); `jotter diff` = what changed SPATIALLY per recorded action —
                                        recover an action's effect from the record WITHOUT re-spending.
  dagger render | plan <goal>           READ the plan graph the sleep pass built (FREE). Use it to
                                        avoid re-deriving what's already structured. You only READ
                                        it — writing the graph is the sleep pass's job, not yours.

Do exactly ONE UNIT OF EXPERIMENT, then STOP. The unit succeeds if it leaves a new durable finding,
whether or not the score moved.
  1. Re-hydrate: `arcg notes`, `arcg actions`, `jotter stats`, `jotter effects`, `jotter diff`, `arcg objects`.
  2. Pick the ONE question whose answer would teach you the MOST and that you don't already know
     (e.g. "what does ACTIONn change? is any action a no-op? what makes the score change?"). Highest
     value is whatever most reduces your uncertainty about the mechanics or the win condition. Don't
     re-derive what `arcg notes` already says.
  3. Test it with the FEWEST real actions: act, then read `arcg diff` to see what YOUR action caused.
     Some cells may change every step regardless of what you do — isolate the part your action caused.
  4. Record the finding durably (one line): `arcg note "<what you learned>"`. Then END YOUR TURN.

Do NOT run `arcg start` or `arcg end` — the harness owns the game lifecycle. One hypothesis tested
and recorded is a complete unit. You have ~14 tool calls — don't dawdle: re-hydrate, act once or
twice, record, stop. Keep it small so the next session can refresh cleanly."""


CONSOLIDATE_TASK = """You are the BACKWARD (sleep) pass of an agent learning ARC-AGI-3. You do NOT
play and spend NO actions. Your job: turn what the waking pass learned into reusable STRUCTURE in
the plan graph, and REMEDIATE the memory — so the next waking pass inherits procedures, not an
ever-growing pile of prose.

Read the accumulated memory (all FREE):
  arcg notes                       the waking pass's prose findings (the compressible scratchpad)
  jotter trace | diff | effects    the grounded, PERMANENT record of what actually happened
  dagger render                    the plan graph so far (what's already consolidated)

Then, in order, then STOP:
  1. CONSOLIDATE a well-grounded, RECURRING pattern as a POSITIVE node — a reliable action effect,
     a sub-procedure that worked, a goal decomposition the evidence supports:
       uv run dagger decompose <anchor> "<goal predicate>" <child-anchor>... --mode sequence|conjunction
     Children are action leaves (ACTION1..7) or other subgoal anchors. REUSE an existing anchor, do
     not mint a synonym. Only consolidate what the trace SUPPORTS; skip one-off guesses and anything
     `dagger render` already has (idempotent — present? do nothing).
  2. ENCODE a falsified plan as a NEGATIVE node (a nogood) so the next pass AVOIDS the dead end
     instead of re-discovering it: `uv run dagger decompose <anchor> "<goal that FAILED>" <child>... --status killed`.
     Do NOT merely forget a falsification — a forgotten dead end gets re-explored and re-wastes budget.
     Encode the negative FIRST.
  3. REMEDIATE the notes: a finding now captured in the graph (positive OR negative) is redundant
     prose — prune it so the next pass re-hydrates clean: `uv run arcg forget "<key phrase>"`. NEVER
     touch jotter — the trace is permanent ground truth; only the prose notes are prunable.
  4. Record one line: `uv run arcg note "CONSOLIDATED <node>; KILLED <node>; pruned <what>"`.

Additive on the graph (positive AND negative), lossy only on the prose. If nothing is well-grounded
enough to consolidate yet, that is fine — say so and STOP. You have ~14 tool calls."""


def _run_session(task: str, allowed: list, *, model: str, max_turns: int, timeout: float) -> dict:
    """Run one fresh agentic claude session with a given task + tool allowlist. Context is fresh each
    call; the durable memory on disk persists. Returns the parsed result (text + cost/turns)."""
    cmd = ["claude", "-p", task, "--output-format", "json", "--model", model,
           "--max-turns", str(max_turns), "--allowedTools", *allowed]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=PROJECT_ROOT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "result": f"(session timed out after {timeout}s)"}
    if proc.returncode != 0:
        return {"ok": False, "result": f"claude exited {proc.returncode}: {proc.stderr[:300]}"}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "result": proc.stdout[:300]}
    return {"ok": not data.get("is_error"), "result": (data.get("result") or "").strip(),
            "turns": data.get("num_turns"), "cost_usd": data.get("total_cost_usd")}


def run_forward_unit(*, model: str = "sonnet", max_turns: int = 14, timeout: float = 300.0) -> dict:
    """One WAKE pass: explore, act, record to jotter+notes; only READ the plan graph."""
    return _run_session(FORWARD_TASK, _FORWARD_ALLOWED, model=model, max_turns=max_turns, timeout=timeout)


def run_backward_unit(*, model: str = "sonnet", max_turns: int = 14, timeout: float = 300.0) -> dict:
    """One SLEEP pass: consolidate grounded patterns into the DAG and remediate the notes. No play."""
    return _run_session(CONSOLIDATE_TASK, _BACKWARD_ALLOWED, model=model, max_turns=max_turns, timeout=timeout)


def run(game: str, *, units: int = 3, cycles: int = 1, budget: int = 20, model: str = "sonnet",
        checkpoint: str | None = None) -> list[dict]:
    """Drive `game` as alternating WAKE/SLEEP cycles, run sequentially. Each cycle: `units` forward
    (explore) sessions that fill jotter+notes, then ONE backward (consolidate) session that writes
    the DAG and remediates the notes. If `checkpoint` is given, RESUME from it and write the grown
    memory back — so learning (incl. the DAG) compounds across runs."""
    cp = Path(checkpoint) if checkpoint else None
    if cp is not None and cp.exists():
        n = _restore_checkpoint(cp)
        print(f"(resumed {n} memory file(s) from checkpoint {cp})")
    l0.start(game, budget_cap=budget)
    log: list[dict] = []
    try:
        for c in range(cycles):
            for i in range(units):                       # WAKE: forward exploration
                sess = store.load_or_none()
                if sess and (sess.state in _TERMINAL
                             or (sess.budget_cap is not None and sess.actions_spent >= sess.budget_cap)):
                    break
                r = run_forward_unit(model=model)
                sess = store.load_or_none()
                r.update(phase="forward", cycle=c + 1,
                         score=sess.score if sess else None,
                         spent=sess.actions_spent if sess else None,
                         state=sess.state if sess else None)
                log.append(r)
            cr = run_backward_unit(model=model)             # SLEEP: consolidate + remediate
            cr.update(phase="consolidate", cycle=c + 1)
            log.append(cr)
    finally:
        if cp is not None:                       # the run's output IS the durable memory (incl. the DAG)
            _save_checkpoint(cp)
    return log


def main() -> None:
    import argparse

    from dotenv import load_dotenv

    load_dotenv()
    p = argparse.ArgumentParser(prog="reason", description="Drive a game as alternating wake/sleep cycles.")
    p.add_argument("game", help="game_id or substring")
    p.add_argument("--units", type=int, default=3, help="forward (explore) sessions per cycle")
    p.add_argument("--cycles", type=int, default=1, help="wake/sleep cycles (each = units forward + 1 consolidate)")
    p.add_argument("--budget", type=int, default=20, help="action cap for the whole run")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--checkpoint", default=None,
                   help="memory dir to RESUME from and write the grown memory back to (learning compounds)")
    args = p.parse_args()
    for r in run(args.game, units=args.units, cycles=args.cycles, budget=args.budget,
                 model=args.model, checkpoint=args.checkpoint):
        if r.get("phase") == "consolidate":
            head = f"--- cycle {r['cycle']} SLEEP/consolidate"
        else:
            head = f"--- cycle {r['cycle']} wake | score {r['score']} | spent {r['spent']} | {r['state']}"
        if r.get("turns"):
            head += f" | {r['turns']} turns ${r.get('cost_usd', 0):.3f}"
        print(head + " ---")
        print((r.get("result") or "").strip()[:600])

    notes = PROJECT_ROOT / ".arc" / "notes.md"
    if notes.exists():
        print("\n=== durable notes (after remediation) ===")
        print(notes.read_text().strip() or "(empty)")
    from .. import dagger
    print("\n=== plan graph (what the sleep pass consolidated) ===")
    print(dagger.render(dagger.connect()))


if __name__ == "__main__":
    main()
