"""jotter CLI — the content-addressed view over piper's transition corpus.

`jotter stats`        — corpus size, unique states, transpositions, revisits.
`jotter has <hash>`   — is this state already known? (exit 0 = yes, 3 = no)
`jotter log`          — the trajectory as state-hashes and actions.
`jotter show <hash>`  — render the grid for a state-hash.
`jotter graph`        — the deduped edge list (from --action--> to).

Corpus is `$ARCG_STATE_DIR/transitions.jsonl`.
"""

from __future__ import annotations

import argparse

import numpy as np

from ..perception import render_grid
from ..session import STATE_DIR
from . import graph

CORPUS = STATE_DIR / "transitions.jsonl"


def stats(m: graph.EpMem) -> str:
    return "\n".join([
        f"corpus transitions : {len(m.order)}",
        f"unique states      : {len(m.states)}",
        f"unique edges       : {len(m.edges)}",
        f"transpositions     : {len(m.transpositions())} (reached >1 way)",
        f"revisits           : {len(m.revisits())} (state seen at >1 step)",
    ])


def log(m: graph.EpMem) -> str:
    if not m.order:
        return "(empty trajectory)"
    return "\n".join(f"{i:3} {hb} --{act}--> {ha}"
                     for i, (hb, act, ha) in enumerate(m.order))


def show(m: graph.EpMem, h: str) -> str:
    if h not in m.states:
        raise SystemExit(f"jotter: no state {h}; never visited — act to reach it")
    return f"state {h}:\n{render_grid(np.asarray(m.states[h], np.int16))}"


def graph_edges(m: graph.EpMem) -> str:
    if not m.edges:
        return "(no edges)"
    seen = sorted({(hb, act, ha) for (hb, act, _x, _y), ha in m.edges.items()})
    return "\n".join(f"{hb} --{act}--> {ha}" for hb, act, ha in seen)


def audit(m: graph.EpMem) -> str:
    """Reconcile jotter against piper. The budget stamps live in the corpus, so this
    audit survives session end (when piper's session.json is gone)."""
    a = m.audit()
    lines = [f"jotter transitions : {a['transitions']}"]
    if a["stamp_range"]:
        lo, hi = a["stamp_range"]
        lines.append(f"piper budget stamps: {lo}..{hi}  "
                     f"({'gapless ✓' if a['gapless'] else 'GAP ✗ — an action went unrecorded'})")
        lines.append(f"count == last stamp: "
                     f"{'✓' if a['count_matches_last_stamp'] else '✗ — drop or duplicate'}")
    else:
        lines.append("piper budget stamps: (none — corpus predates the counter)")
    sess = STATE_DIR / "session.json"
    if sess.exists():
        import json
        s = json.loads(sess.read_text())
        spent = s.get("actions_spent")
        lines.append(f"piper actions_spent: {spent}  vs jotter {a['transitions']}  "
                     f"({'MATCH ✓' if spent == a['transitions'] else 'MISMATCH ✗ — investigate'})")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(prog="jotter", description="Content-addressed episodic memory.")
    p.add_argument("--corpus", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats", help="corpus / graph summary").set_defaults(fn=stats, want=None)
    sub.add_parser("audit", help="reconcile against piper via budget stamps").set_defaults(fn=audit, want=None)
    sub.add_parser("log", help="trajectory").set_defaults(fn=log, want=None)
    sub.add_parser("graph", help="deduped edge list").set_defaults(fn=graph_edges, want=None)
    sh = sub.add_parser("show", help="render a state's grid"); sh.add_argument("hash"); sh.set_defaults(fn=show, want="hash")
    ha = sub.add_parser("has", help="is this state known? exit 0=yes 3=no"); ha.add_argument("hash"); ha.set_defaults(fn=None, want="hash")
    args = p.parse_args()

    from pathlib import Path
    m = graph.load(Path(args.corpus) if args.corpus else CORPUS)

    if args.cmd == "has":
        known = m.has(args.hash)
        print("known" if known else "novel")
        raise SystemExit(0 if known else 3)
    print(args.fn(m, args.hash) if args.want else args.fn(m))


if __name__ == "__main__":
    main()
