"""dagger CLI — inspect and grow the Action DAG (the plan graph).

`dagger render`                      the whole graph as markdown (db -> prose, for inspection)
`dagger plan <goal>`                 JIT: a cached decomposition (HIT) or a HOLE to abduce (miss)
`dagger get <ref>`                   resolve a dagger:<anchor> ref to a node, or MISS
`dagger decompose <anchor> <goal> <child>... [--mode sequence|conjunction]`
                                     write a decomposition of <goal> into child anchors
`dagger init <action>...`            seed apex `win-game` + one leaf per action

Store is `$ARCG_STATE_DIR/graph.db` (a SQLite jotter submodule). Identity is the authored ANCHOR.
"""

from __future__ import annotations

import argparse

from . import dag


def _fmt(n) -> str:
    body = f"action {n.action}" if n.is_leaf else f"{n.mode}: {' ; '.join(n.children) or '(none)'}"
    prov = "" if n.is_leaf else f", {n.provenance}"
    ev = f"  evidence={list(n.evidence)}" if n.evidence else ""
    return f"  {n.ref()}  [{n.kind}, {n.status}{prov}]  post={n.post!r}  {body}{ev}"


_CONTRACT = """\
dagger — the Action DAG (procedural memory, pmem).

The SLEEP pass consolidates episodic memory (jotter: the grounded trace + the waking notes)
into procedures here. The goal is not to consolidate as much as possible — it is to promote
what the evidence CLEANLY grounds and LEAVE THE AMBIGUOUS ONES for the next sleep pass. A
forced verdict is worse than a deferred one.

  render                 the whole graph as markdown (read it first)
  plan <goal>            a cached decomposition (HIT) or a HOLE to abduce (miss)
  get <ref>             resolve a dagger:<anchor> ref to a node
  decompose ...         write/promote a node  (see `dagger decompose --help` — the discipline)
  init <action>...      seed apex win-game + one leaf per action

Pull specifics from `dagger <cmd> --help`. Store is $ARCG_STATE_DIR/graph.db; identity is the anchor."""

_DECOMPOSE_EPILOG = """\
A node is a procedure consolidated from episodes. Its status is how SECURED it is, and that
governs what it must cite:

  open    a DREAM — a hypothesis for a later pass to test. Evidence optional; renders
          `speculative`. This is where AMBIGUOUS patterns belong: if the episodes don't yet
          cleanly settle it, write it open and leave it for the next sleep pass. Don't force it.
  live    a positive VERDICT. Must cite the episode(s) that establish it.
  killed  a NEGATIVE/nogood — a plan the trace disproved, so a later pass avoids re-exploring it.
          A verdict too: cite the episode(s).

A CAUSAL/conditional post (one naming a cause: "blocked WHEN ...", "drags ...", "because ...")
needs a CONTRAST PAIR — >=2 refs, one where it holds and one where it doesn't — because a
single episode can't isolate a cause. Before you assert it, run `jotter show <a> <b>` on the
pair and CONFIRM the cause you name is the feature that DIFFERS across them. If it is constant
across the pair, it is NOT the cause: pick the feature that actually varies, or leave the node
`open`. (This is the gate that stops a confident-but-hallucinated nogood.)"""


def main() -> None:
    p = argparse.ArgumentParser(prog="dagger", description="The Action DAG (plan graph).",
                                epilog=_CONTRACT, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("render", help="the whole graph as markdown")
    g = sub.add_parser("get", help="resolve a dagger:<anchor> ref to a node")
    g.add_argument("ref")
    pl = sub.add_parser("plan", help="cached decomposition (HIT) or a HOLE (miss)")
    pl.add_argument("goal")
    d = sub.add_parser("decompose", help="write/promote a node consolidated from episodes",
                       epilog=_DECOMPOSE_EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    d.add_argument("anchor")
    d.add_argument("goal")
    d.add_argument("children", nargs="+", help="child anchors (2+ to branch; the suggested floor)")
    d.add_argument("--mode", choices=("sequence", "conjunction"), default="sequence")
    d.add_argument("--status", choices=("open", "live", "killed"), default="open",
                   help="open = a speculative DREAM (leave ambiguous ones here); live/killed = a "
                        "VERDICT that must cite evidence (killed = a nogood). See the epilog below.")
    d.add_argument("--evidence", default="",
                   help="comma-separated jotter refs (step indices or state hashes) this post is "
                        "attributed to. Optional for `open`; a live/killed VERDICT must cite them, "
                        "and a causal post needs a contrast pair (2+) that ISOLATES the cause.")
    i = sub.add_parser("init", help="seed apex + one leaf per action")
    i.add_argument("actions", nargs="+")
    args = p.parse_args()

    if args.cmd is None:                 # no-args: print the driving-contract (progressive disclosure)
        print(_CONTRACT)
        return

    conn = dag.connect()
    if args.cmd == "render":
        print(dag.render(conn))
    elif args.cmd == "get":
        n = dag.get(conn, args.ref)
        print("MISS" if n is None else _fmt(n))
    elif args.cmd == "plan":
        r = dag.plan(conn, args.goal)
        if isinstance(r, dag.Hole):
            print(f"HOLE: no decomposition for {args.goal!r} — abduce one with `dagger decompose`")
        else:
            print(f"HIT\n{_fmt(r)}")
    elif args.cmd == "decompose":
        evidence = [e.strip() for e in args.evidence.split(",") if e.strip()]
        try:
            n = dag.decompose(conn, args.anchor, args.goal, args.children, args.mode,
                              args.status, evidence)
        except ValueError as e:
            raise SystemExit(str(e))
        print(f"wrote {n.ref()}\n{_fmt(n)}")
    elif args.cmd == "init":
        dag.init(conn, args.actions)
        print(f"seeded: win-game + {len(args.actions)} leaves")


if __name__ == "__main__":
    main()
