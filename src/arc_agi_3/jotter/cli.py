"""jotter CLI — the content-addressed view over piper's transition corpus.

`jotter stats`        — corpus size, unique states, transpositions, revisits.
`jotter has <hash>`   — is this state already known? (exit 0 = yes, 3 = no)
`jotter log`          — the trajectory as state-hashes and actions.
`jotter show <hash>`  — render the grid for a state-hash.
`jotter graph`        — the deduped edge list (from --action--> to).
`jotter effects`      — grounded per-action count deltas (resource/quantity facts).
`jotter diff [i]`     — spatial delta per recorded action (what MOVED; the twin of effects).
`jotter audit`        — reconcile the corpus against piper's budget stamps.
`jotter trace`        — content-addressed trace of the play (the series-evidence object).

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


def effects_report(path) -> str:
    """Grounded per-action effects from the record — the resource/quantity facts (the bar
    depletes, tokens consumed, score moves) a driver should CHECK here, not estimate. A
    non-constant distribution (e.g. `11: -2×11, -4×24`) exposes a rate that isn't fixed."""
    import json
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    if not rows:
        return "(empty corpus — play with piper first)"
    eff = graph.effects(rows)
    lines = ["grounded per-action effects (colour: count-delta ×occurrences), from the record:"]
    for a in sorted(eff, key=lambda a: str(a)):
        lines.append(f"  {a}:")
        for c in sorted(eff[a], key=lambda c: -sum(eff[a][c].values())):
            dist = ", ".join(f"{d:+d}×{n}" for d, n in sorted(eff[a][c].items()))
            lines.append(f"    colour {c:>2}: {dist}")
    return "\n".join(lines)


def diff_report(path, index) -> str:
    """The SPATIAL story of the trace (what MOVED per action), via piper's perception. The twin of
    `effects`: movement is count-conserved, so it shows here but not in the count deltas. Lets a
    fresh session recover an action's effect from the record without re-spending budget."""
    import json
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    if not rows:
        return "(empty corpus — play with piper first)"
    if index is None:
        lines = ["spatial delta per recorded action (what changed, from the trace):"]
        for i, t in enumerate(rows):
            d = graph.transition_diff(t["before"], t["after"])
            coord = f" ({t.get('x')},{t.get('y')})" if t.get("x") is not None else ""
            lines.append(f"  [{i}] {t['action']}{coord}: {d.describe(max_cells=6)}")
        return "\n".join(lines)
    if not 0 <= index < len(rows):
        raise SystemExit(f"jotter: index {index} out of range (0-{len(rows)-1})")
    t = rows[index]
    d = graph.transition_diff(t["before"], t["after"])
    return (f"[{index}] {t['action']} (x={t.get('x')}, y={t.get('y')}) spatial delta:\n"
            f"{d.describe(max_cells=60)}")


def trace_report(path) -> str:
    """The content-addressed trace of the recorded play — the series-evidence object, with a
    stable id you can cite as provenance (re-recording the same play reproduces it)."""
    import json
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    tr = graph.trace(rows)
    if not tr["id"]:
        return "(empty corpus — play with piper first)"
    lines = [f"trace {tr['id']}  ({tr['len']} steps)  "
             f"initial {tr['initial']} -> final {tr['final']}"]
    for i, s in enumerate(tr["steps"]):
        coord = f" ({s['x']},{s['y']})" if s["x"] is not None else ""
        lines.append(f"{i:3} {s['before']} --{s['action']}{coord}--> {s['after']}")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(prog="jotter", description="Content-addressed episodic memory.")
    p.add_argument("--corpus", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats", help="corpus / graph summary").set_defaults(fn=stats, want=None)
    sub.add_parser("effects", help="grounded per-action effects (resource/quantity facts, from the record)").set_defaults(fn=None, want=None)
    sub.add_parser("trace", help="content-addressed trace of the recorded play (the series-evidence object)").set_defaults(fn=None, want=None)
    df = sub.add_parser("diff", help="spatial delta per recorded action (what MOVED; the twin of effects)")
    df.add_argument("index", type=int, nargs="?", default=None)
    df.set_defaults(fn=None, want=None)
    sub.add_parser("audit", help="reconcile against piper via budget stamps").set_defaults(fn=audit, want=None)
    sub.add_parser("log", help="trajectory").set_defaults(fn=log, want=None)
    sub.add_parser("graph", help="deduped edge list").set_defaults(fn=graph_edges, want=None)
    sh = sub.add_parser("show", help="render a state's grid"); sh.add_argument("hash"); sh.set_defaults(fn=show, want="hash")
    ha = sub.add_parser("has", help="is this state known? exit 0=yes 3=no"); ha.add_argument("hash"); ha.set_defaults(fn=None, want="hash")
    args = p.parse_args()

    from pathlib import Path
    corpus_path = Path(args.corpus) if args.corpus else CORPUS

    if args.cmd == "effects":          # reads raw transitions (count facts), not the dedup graph
        print(effects_report(corpus_path))
        return

    if args.cmd == "trace":            # reads raw transitions in order (the series), not the graph
        print(trace_report(corpus_path))
        return

    if args.cmd == "diff":             # spatial delta per recorded transition (what moved)
        print(diff_report(corpus_path, args.index))
        return

    m = graph.load(corpus_path)

    if args.cmd == "has":
        known = m.has(args.hash)
        print("known" if known else "novel")
        raise SystemExit(0 if known else 3)
    print(args.fn(m, args.hash) if args.want else args.fn(m))


if __name__ == "__main__":
    main()
