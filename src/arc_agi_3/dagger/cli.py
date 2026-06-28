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


def main() -> None:
    p = argparse.ArgumentParser(prog="dagger", description="The Action DAG (plan graph).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("render", help="the whole graph as markdown")
    g = sub.add_parser("get", help="resolve a dagger:<anchor> ref to a node")
    g.add_argument("ref")
    pl = sub.add_parser("plan", help="cached decomposition (HIT) or a HOLE (miss)")
    pl.add_argument("goal")
    d = sub.add_parser("decompose", help="write a decomposition of <goal> into child anchors")
    d.add_argument("anchor")
    d.add_argument("goal")
    d.add_argument("children", nargs="+", help="child anchors (2+ to branch; the suggested floor)")
    d.add_argument("--mode", choices=("sequence", "conjunction"), default="sequence")
    d.add_argument("--status", choices=("open", "live", "killed"), default="open",
                   help="killed = a NEGATIVE/nogood: a plan the trace disproved, to avoid re-exploring")
    d.add_argument("--evidence", default="",
                   help="comma-separated jotter refs (step indices or state hashes) this post is "
                        "attributed to. Optional for `open` (speculative); a live/killed VERDICT "
                        "must cite them, and a causal post needs a contrast pair (2+).")
    i = sub.add_parser("init", help="seed apex + one leaf per action")
    i.add_argument("actions", nargs="+")
    args = p.parse_args()

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
