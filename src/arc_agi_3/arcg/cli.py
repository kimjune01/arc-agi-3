"""arcg CLI — the single entry point. Dispatches to the layer functions.

The dispatcher sits above the stack, so it may import every layer. Each
subcommand calls one layer function and prints its returned string; the same
functions are what a programmatic policy calls (one shared surface).
"""

from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

from . import layer0_protocol as l0
from . import layer1_intent as l1
from . import layer2_state as l2
from . import layer3_memory as l3
from . import trace

# Each command's home layer, so every trace event is tagged ("each layer emits its
# own traces" — one stream tagged by layer while arcg is a single CLI; per-module
# files once the five modules are split into separate processes).
_LAYER = {
    "games": 0, "start": 0, "act": 0, "reset": 0, "end": 0,
    "move": 1, "interact": 1, "click": 1, "undo": 1, "look": 1, "diff": 1, "objects": 1, "actions": 1,
    "history": 2, "snapshot": 2, "restore": 2, "peek": 2,
    "note": 3, "notes": 3, "forget": 3,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="arcg", description="ARC-AGI-3 layered agent tools.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help, args=()):
        sp = sub.add_parser(name, help=help)
        for a, kw in args:
            sp.add_argument(a, **kw)
        sp.set_defaults(fn=fn)
        return sp

    # Layer 0 — protocol
    add("games", lambda a: l0.games(), "list game ids")
    add("start", lambda a: l0.start(a.game, tags=a.tags, budget_cap=a.budget),
        "open scorecard, reset, show frame",
        [("game", {}), ("--tags", {}), ("--budget", {"type": int,
         "help": "tight action cap for test runs (~5x human); terminate when hit"})])
    add("act", lambda a: _fmt(l0.act(a.action, x=a.x, y=a.y,
                                     dagger=a.dagger, arbor=a.arbor)),
        "raw ACTION1..7 (escape hatch)",
        [("action", {}), ("--x", {"type": int}), ("--y", {"type": int}),
         # The escape hatch still names its provenance: a manual op defaults to the
         # manual plan node + an open manual hypothesis. The driver passes real refs.
         ("--dagger", {"default": "dagger:manual",
          "help": "plan-node ref this action executes (dagger:<id>)"}),
         ("--arbor", {"default": "arbor:#manual",
          "help": "hypothesis ref this action tests (arbor:#<id>)"})])
    add("reset", lambda a: _fmt(l0.reset(full=not a.level)),
        "RESET (full by default; --level restarts current level)",
        [("--level", {"action": "store_true"})])
    add("end", lambda a: l0.end(), "close scorecard, clear session")

    # Layer 1 — intent + perception
    add("move", lambda a: l1.move(a.direction), "move up/down/left/right",
        [("direction", {"choices": list(l1.INTENT)})])
    add("interact", lambda a: l1.interact(), "ACTION5 interact/select")
    add("click", lambda a: l1.click(a.x, a.y), "click/place at x,y (ACTION6)",
        [("x", {"type": int}), ("y", {"type": int})])
    add("undo", lambda a: l1.undo(), "undo last action (ACTION7)")
    add("actions", lambda a: l1.available(), "list the currently available actions")
    add("look", lambda a: l1.look(no_grid=a.no_grid), "render current observation",
        [("--no-grid", {"action": "store_true"})])
    add("diff", lambda a: l1.diff(), "delta since last action")
    add("objects", lambda a: l1.objects(with_bg=a.with_bg,
                                        connectivity=8 if a.diag else 4),
        "connected-component objects (spatial edges) in the current frame",
        [("--with-bg", {"action": "store_true",
          "help": "include the background (modal) colour"}),
         ("--diag", {"action": "store_true",
          "help": "8-connectivity (count diagonals as touching)"})])

    # Layer 2 — state & determinism
    add("history", lambda a: l2.history(), "action sequence + budget + snapshots")
    add("snapshot", lambda a: l2.snapshot(a.label), "name the current sequence",
        [("label", {})])
    add("restore", lambda a: l2.restore(a.label), "reset+replay to a snapshot",
        [("label", {})])
    add("peek", lambda a: l2.peek(a.label), "cache-only view of a snapshot (free)",
        [("label", {})])

    # Layer 3 — memory
    add("note", lambda a: l3.note(a.text), "append a finding", [("text", {})])
    add("notes", lambda a: l3.notes(), "list findings")
    add("forget", lambda a: l3.forget(a.match, all_=a.all),
        "prune notes already compressed to structure, or falsified (consolidation cleanup)",
        [("match", {"nargs": "?", "default": None}), ("--all", {"action": "store_true"})])
    return p


def _fmt(frame) -> str:
    return (f"raw frame | state {frame.state.value} | score {frame.score}/"
            f"{frame.win_score} | available {[a.name for a in frame.available_actions]}")


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    base = {
        "tool": "arcg", "layer": _LAYER.get(args.cmd), "cmd": args.cmd,
        "args": {k: v for k, v in vars(args).items() if k not in ("fn", "cmd", "layer")},
    }
    start = time.perf_counter()
    try:
        out = args.fn(args)
    except BaseException as e:  # trace the failure, then preserve original behavior
        trace.emit({**base, "ok": False, "error": str(e),
                    "ms": round((time.perf_counter() - start) * 1000, 1)})
        if isinstance(e, l0.BudgetExceeded):
            raise SystemExit(f"TERMINATED: {e}")
        raise
    trace.emit({**base, "ok": True,
                "ms": round((time.perf_counter() - start) * 1000, 1)})
    print(out)


if __name__ == "__main__":
    main()
