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
    g = m.states[h]
    if g is None:                                              # grid evicted (compressed away)
        return f"state {h}: (evicted — grid compressed away; replay or simmer to regenerate)"
    return f"state {h}:\n{render_grid(np.asarray(g, np.int16))}"


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
    rows = [t for t in rows if not graph.is_stub(t)]           # evicted stubs have no grid to diff
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
            coord = f" ({t.get('x')},{t.get('y')})" if t.get("x") is not None else ""
            if graph.is_stub(t):                               # grid evicted — no spatial delta to show
                lines.append(f"  [{i}] {t['action']}{coord}: (evicted; replay to regenerate)")
                continue
            d = graph.transition_diff(t["before"], t["after"])
            lines.append(f"  [{i}] {t['action']}{coord}: {d.describe(max_cells=6)}")
        return "\n".join(lines)
    if not 0 <= index < len(rows):
        raise SystemExit(f"jotter: index {index} out of range (0-{len(rows)-1})")
    t = rows[index]
    if graph.is_stub(t):
        raise SystemExit(f"jotter: transition {index} is evicted (grid compressed away) — replay to regenerate")
    d = graph.transition_diff(t["before"], t["after"])
    return (f"[{index}] {t['action']} (x={t.get('x')}, y={t.get('y')}) spatial delta:\n"
            f"{d.describe(max_cells=60)}")


def trace_report(path) -> str:
    """The content-addressed trace of the recorded play — the series-evidence object, with a
    stable id you can cite as provenance (re-recording the same play reproduces it)."""
    import json
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    tr = graph.trace(rows, _counter(path, rows))
    if not tr["id"]:
        return "(empty corpus — play with piper first)"
    lines = [f"trace {tr['id']}  ({tr['len']} steps)  "
             f"initial {tr['initial']} -> final {tr['final']}"]
    for i, s in enumerate(tr["steps"]):
        coord = f" ({s['x']},{s['y']})" if s["x"] is not None else ""
        lines.append(f"{i:3} {s['before']} --{s['action']}{coord}--> {s['after']}")
    return "\n".join(lines)


def _rows(path) -> list:
    import json
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def _ledger(corpus_path):
    """The consolidation ledger sits beside the corpus — a SIDECAR, so the grounded trace stays
    append-only and untouched. It records which deduped edges have been consolidated (spent)."""
    return corpus_path.parent / "consolidated.jsonl"


def _spent_keys(ledger_path) -> frozenset:
    import json
    if not ledger_path.exists():
        return frozenset()
    return frozenset(json.loads(l)["key"] for l in ledger_path.read_text().splitlines() if l.strip())


def _detect_counter(rows):
    full = [t for t in rows if not graph.is_stub(t)]            # evicted stubs carry no grid to mask
    return graph.detect_counter([full[0]["before"]] + [t["after"] for t in full]) if full else frozenset()


def _counter(corpus_path, rows):
    """The counter to hash with: the PINNED one if consolidation has frozen it (so full rows and
    evicted stubs stay consistent), else freshly detected. Pinned wins even if empty."""
    pinned = graph.load_counter(corpus_path)
    return pinned if pinned is not None else _detect_counter(rows)


def pending_report(path, ledger_path) -> str:
    """The ADMISSION SET — deduped, un-consolidated episodes — for the sleep pass to translate. The
    cheap mechanical filter: dedup is free (content-addressed), spent ones are excluded, so the
    expensive LLM only sees what's actually new."""
    rows = _rows(path)
    if not rows:
        return "(empty corpus — play with piper first)"
    counter = _counter(path, rows)
    spent = _spent_keys(ledger_path)
    pend = graph.pending_edges(rows, counter, spent)
    head = (f"pending (deduped, un-consolidated): {len(pend)} of "
            f"{len(graph.unique_edges(rows, counter))} unique edges  ({len(spent)} spent)")
    if not pend:
        return head + "\n  (nothing pending — all consolidated)"
    lines = [head]
    for e in pend:
        coord = f" ({e['x']},{e['y']})" if e["x"] is not None else ""
        d = graph.transition_diff(rows[e["idx"]]["before"], rows[e["idx"]]["after"])
        lines.append(f"  [{e['idx']}] {e['before']} --{e['action']}{coord}--> "
                     f"{e['after']} : {d.describe(max_cells=4)}")
    return "\n".join(lines)


def spend(path, ledger_path, indices, into) -> str:
    """Tombstone episodes as consolidated — append their content-keys to the ledger so `pending`
    shrinks. Idempotent (a key already spent is skipped). Resolves ANY step index to its deduped
    edge, so spending a repeat works. Does NOT touch the grounded corpus."""
    import json
    rows = _rows(path)
    if not rows:
        raise SystemExit("jotter: empty corpus — nothing to spend")
    counter = _counter(path, rows)
    existing = set(_spent_keys(ledger_path))
    added = 0
    with ledger_path.open("a") as f:
        for i in indices:
            if not 0 <= i < len(rows):
                raise SystemExit(f"jotter: index {i} out of range (0-{len(rows) - 1})")
            t = rows[i]
            k = graph.edge_key(graph.state_hash(t["before"], counter), t["action"],
                               t.get("x"), t.get("y"), graph.state_hash(t["after"], counter))
            if k in existing:                                  # idempotent: already spent
                continue
            f.write(json.dumps({"key": k, "idx": i, "into": into}) + "\n")
            existing.add(k)
            added += 1
    rem = len(graph.pending_edges(rows, counter, frozenset(existing)))
    return f"spent {added} episode(s){f' into {into}' if into else ''}; {rem} pending"


def evict(path, ledger_path, dry_run: bool) -> str:
    """COMPRESSION (the sleep-prune): drop the heavy grids of CONSOLIDATED (spent) transitions,
    leaving a hash-stub (action + coords + before/after hashes + budget stamp). The ordered ACTION
    LOG and the content identity survive — only the renderable grid goes, and it's regenerable via
    replay (or simmer, where the rule models it). Loose by design: a wrong evict costs a re-derive,
    not corruption (the deterministic action log is the backstop). Un-spent episodes keep their
    grids. `--dry-run` reports without rewriting."""
    import json
    rows = _rows(path)
    if not rows:
        return "(empty corpus — nothing to evict)"
    counter = _counter(path, rows)
    spent = _spent_keys(ledger_path)
    out, n, saved = [], 0, 0
    for t in rows:
        if graph.is_stub(t):
            out.append(t)
            continue
        hb = graph.state_hash(t["before"], counter)
        ha = graph.state_hash(t["after"], counter)
        if graph.edge_key(hb, t["action"], t.get("x"), t.get("y"), ha) in spent:
            stub = {"action": t["action"], "x": t.get("x"), "y": t.get("y"),
                    "before": hb, "after": ha, "evicted": True}
            if t.get("spent") is not None:                      # keep piper's BUDGET stamp (audit/replay)
                stub["spent"] = t["spent"]
            saved += len(json.dumps(t)) - len(json.dumps(stub))
            out.append(stub)
            n += 1
        else:
            out.append(t)                                       # un-spent: keep the full grid
    if not dry_run and n:
        graph.save_counter(path, counter)                      # PIN the mask so stubs + future rows stay consistent
        path.write_text("".join(json.dumps(r) + "\n" for r in out))
    verb = "would evict" if dry_run else "evicted"
    return (f"{verb} {n} consolidated episode(s)' grids (~{saved} bytes reclaimed); "
            f"action log + hashes + budget stamps kept")


_CONTRACT = """\
jotter — episodic memory (epmem): the content-addressed, PERMANENT record of what happened.

The grounded trace is append-only ground truth — the evidence pmem nodes cite, never pruned. The
consolidation pipe reads it through a cheap mechanical filter:

  stats | trace | log | graph    the deduped state graph + trajectory
  diff [i] | effects | show      what an action did (spatial / count), recovered without re-spending
  pending                        the ADMISSION SET — deduped, un-consolidated episodes (the cheap filter)
  spend <idx>... --into <node>   tombstone episodes as consolidated, so `pending` shrinks
  evict [--dry-run]              compress: drop the grids of consolidated episodes (keep action log + hashes)
  has <hash> | audit             membership; reconcile vs piper's budget stamps

Pull specifics from `jotter <cmd> --help`. Corpus is $ARCG_STATE_DIR/transitions.jsonl; the spent
ledger is a sidecar (consolidated.jsonl), so the trace itself stays untouched."""


def main() -> None:
    p = argparse.ArgumentParser(prog="jotter", description="Content-addressed episodic memory.",
                                epilog=_CONTRACT, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", default=None)
    sub = p.add_subparsers(dest="cmd")
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
    pe = sub.add_parser("pending", help="admission set: deduped, un-consolidated episodes (the cheap filter)")
    pe.set_defaults(fn=None, want=None)
    sp = sub.add_parser("spend", help="tombstone episodes as consolidated into a node (so pending shrinks)")
    sp.add_argument("index", type=int, nargs="+")
    sp.add_argument("--into", default=None, help="the dagger anchor they were consolidated into")
    sp.set_defaults(fn=None, want=None)
    ev = sub.add_parser("evict", help="compress: drop grids of consolidated episodes, keep action log + hashes")
    ev.add_argument("--dry-run", action="store_true", help="report what would be evicted without rewriting")
    ev.set_defaults(fn=None, want=None)
    args = p.parse_args()

    if args.cmd is None:               # no-args: the driving-contract (progressive disclosure)
        print(_CONTRACT)
        return

    from pathlib import Path
    corpus_path = Path(args.corpus) if args.corpus else CORPUS

    if args.cmd == "pending":          # the cheap admission filter (deduped, un-spent)
        print(pending_report(corpus_path, _ledger(corpus_path)))
        return

    if args.cmd == "spend":            # tombstone consolidated episodes (sidecar ledger)
        print(spend(corpus_path, _ledger(corpus_path), args.index, args.into))
        return

    if args.cmd == "evict":            # compress: drop consolidated grids, keep action log + hashes
        print(evict(corpus_path, _ledger(corpus_path), args.dry_run))
        return

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
