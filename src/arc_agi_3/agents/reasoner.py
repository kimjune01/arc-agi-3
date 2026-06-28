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
_TERMINAL = ("WIN", "GAME_OVER", "NOT_STARTED")  # NOT_STARTED = run ended, awaiting RESET

# The durable memories — the agent's actual product. A checkpoint is a copy of these; resuming from
# one is how learning compounds across runs (and how it transfers to another agent/machine).
MEMORY_FILES = ("notes.md", "transitions.jsonl", "graph.db", "consolidated.jsonl", "counter.json")

# The tool allowlists ENFORCE the read/write split between the two passes (not just the prompt):
#   FORWARD (wake/explore) acts the game and writes jotter + notes; it only READS dagger (the plan
#     the sleep pass built) — render/plan/get, never decompose.
#   BACKWARD (sleep/consolidate) reads everything and WRITES dagger (decompose); it never plays
#     (no `arcg act` — only `arcg note`/`notes`).
_FORWARD_ALLOWED = ["Bash(uv run arcg:*)", "Bash(uv run jotter:*)",
                    "Bash(uv run simmer:*)",                            # FREE rollout (predict before spending)
                    "Bash(uv run dagger render:*)", "Bash(uv run dagger plan:*)",
                    "Bash(uv run dagger get:*)"]
_BACKWARD_ALLOWED = ["Bash(uv run arcg notes:*)", "Bash(uv run arcg note:*)",
                     "Bash(uv run arcg forget:*)",
                     "Bash(uv run jotter:*)", "Bash(uv run simmer:*)",  # test the engine vs the corpus
                     "Bash(uv run dagger:*)"]


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

FORWARD_TASK = """You are the WAKE pass of an agent studying ARC-AGI-3, an unknown 64x64 grid \
game already in progress (the harness owns its lifecycle — do NOT start/end it). You know nothing \
about the rules; learn only by acting and watching what changes. You are a FRESH session — your \
memory is on disk, so re-hydrate before acting.

GOAL: make ONE ATTEMPT that grows episodic memory. Pick your best current question (what does an \
action do? is any a no-op? what moves the score? once the moves are mapped, drive into walls and \
edges — a BLOCKED move is as much an episode as one that moves), spend ONE real action to test it, \
and record what happened. You do NOT need a clean, consolidate-worthy result: an inconclusive or \
messy episode is fine — the SLEEP pass sorts epmem into pmem and leaves the ambiguous ones. \
Episodic memory ACCUMULATING is expected and OK; your job is the ATTEMPT, not a polished finding. \
Score moving is only a signal to learn from.

Inspection is free, and so is `simmer predict` — a FREE rollout of an action's effect on the \
current grid (deduction). PREDICT in simmer first; spend the REAL `arcg act` (budget) to actually \
make the attempt — that paid action, and the episode it records, IS the unit's product. That is \
the model-based core: plan in simmer, commit in piper.

SELF-STOP (the bound is your goal, not a turn count): once you've made your attempt — acted and \
recorded what happened — STOP. Don't hunt for a perfect question or a cleaner finding, and don't \
re-inspect memory you've already read; that is how a unit burns to timeout. Re-hydrate ONCE, make \
your attempt, record, stop.

Tools — run `uv run <tool> ...` from the repo root; pull specifics from `<tool> --help`:
  arcg    actions | objects | diff | act | note — available actions; perceive; ACT (costs budget); record a finding
  simmer  predict — FREE: predict an action's effect on the current grid BEFORE spending a real one
  jotter  stats | effects | diff | trace — the grounded record; recover an action's effect WITHOUT re-spending
  dagger  render | plan — READ the plan graph the sleep pass built (you only read it)

Re-hydrate (`arcg notes`, `jotter trace`, `dagger render`, `arcg objects`), predict in simmer, \
spend a real action only where simmer is untrustworthy, `arcg note` the finding, then STOP."""


CONSOLIDATE_TASK = """You are the SLEEP pass of an agent learning ARC-AGI-3. You do NOT play \
(spend no actions).

GOAL: consolidate episodic memory into procedural memory, as a CHEAP-FILTER-then-translate pipe. \
Work the ADMISSION SET — `jotter pending`, the deduped, un-consolidated episodes — NOT the whole \
trace (dedup is already done for you; don't re-judge what's consolidated). For each pattern the \
evidence CLEANLY grounds: `dagger decompose` it (citing the episodes), then `jotter spend` those \
episodes so they leave the pending set. LEAVE THE AMBIGUOUS ONES un-spent (no isolating contrast \
pair, or conflicting evidence) — they stay pending for the next pass; a forced verdict is worse \
than a deferred one. Then prune the notes you captured. When the clean pending episodes are \
consolidated-and-spent and their notes pruned, STOP. If nothing is cleanly groundable yet, STOP.

Tools — run `uv run <tool> ...` from the repo root; pull specifics from `<tool> --help`:
  jotter  pending | spend | diff | show — the ADMISSION SET to consolidate; tombstone the consolidated \
ones; the evidence you cite (never prune the trace)
  simmer  test — replay the corpus; a MISS means don't promote a mechanic the engine can't reproduce
  dagger  render | decompose — write/promote a node. `dagger decompose --help` IS the discipline: \
what a verdict must cite, and when to leave a node open
  arcg    notes | forget | note — read the prose findings; prune captured ones; record a one-line summary

Per clean pattern in `jotter pending`: decompose (cite the episodes) → `jotter spend <those idxs> \
--into <anchor>`. Leave ambiguous episodes pending. Prune redundant notes, record one line, STOP."""


def _build_cmd(task: str, allowed: list, *, model: str, max_turns: int | None) -> list[str]:
    """The `claude` invocation for one session. `max_turns=None` adds NO `--max-turns` flag: the
    session is bounded by its GOAL (the prompt's STOP), not a hard turn cap. A hard cap starves a
    pass mid-unit (it once cut the sleep pass off before remediation); goal-based termination doesn't."""
    cmd = ["claude", "-p", task, "--output-format", "json", "--model", model]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]
    return cmd + ["--allowedTools", *allowed]


def _run_session(task: str, allowed: list, *, model: str, max_turns: int | None, timeout: float) -> dict:
    """Run one fresh agentic claude session with a given task + tool allowlist. Context is fresh each
    call; the durable memory on disk persists. Returns the parsed result (text + cost/turns). The
    session self-terminates at its goal; `timeout` is only the runaway backstop (the andon cord)."""
    cmd = _build_cmd(task, allowed, model=model, max_turns=max_turns)
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


def run_forward_unit(*, model: str = "sonnet", max_turns: int | None = None, timeout: float = 300.0) -> dict:
    """One WAKE pass: explore, act, record to jotter+notes; only READ the plan graph. Bounded by its
    GOAL (one recorded finding, then STOP), not a turn count; `timeout` is the runaway backstop."""
    return _run_session(FORWARD_TASK, _FORWARD_ALLOWED, model=model, max_turns=max_turns, timeout=timeout)


def run_backward_unit(*, model: str = "sonnet", max_turns: int | None = None, timeout: float = 660.0) -> dict:
    """One SLEEP pass: consolidate grounded patterns into the DAG and remediate the notes. No play.
    Bounded by its GOAL (consolidate the clean patterns, leave the ambiguous ones, prune, STOP), not
    a turn count — a hard cap once starved this pass before remediation. `timeout` (wider than a wake
    unit's: it reads everything, writes several nodes, self-checks each causal verdict) is the only
    backstop."""
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
            cr = run_backward_unit(model=model)             # SLEEP: consolidate + remediate (LLM judgment)
            corpus = STATE_DIR / "transitions.jsonl"        # sleep-prune: compress what was consolidated
            if corpus.exists():                             # MECHANICAL (harness computes; not the LLM's call)
                from ..jotter import cli as _jc
                cr["evict"] = _jc.evict(corpus, _jc._ledger(corpus), dry_run=False)
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
