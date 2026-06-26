"""simmer CLI — differentially test the hand-edited engine against piper's corpus.

`simmer test`  — replay every recorded transition through `step`; report which the
                 engine reproduces and, for misses, WHERE it diverges (the refine signal).
`simmer step`  — apply `step` to one corpus transition's before-state and show the
                 predicted grid plus its diff against reality.

The corpus is `$ARCG_STATE_DIR/transitions.jsonl`, written by piper as you play.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from ..perception import diff_grids, render_grid
from ..session import STATE_DIR
from .engine import step

CORPUS = STATE_DIR / "transitions.jsonl"


def _load(path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"simmer: no corpus at {path} — play with piper first "
                         f"(set ARCG_STATE_DIR to the run dir).")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test(path) -> str:
    trans = _load(path)
    lines, npass = [], 0
    for i, t in enumerate(trans):
        before = np.asarray(t["before"], np.int16)
        after = np.asarray(t["after"], np.int16)
        pred = np.asarray(step(before, t["action"], t.get("x"), t.get("y")), np.int16)
        d = diff_grids(after, pred)  # pred vs reality: 0 changed == reproduced
        if d.changed == 0:
            npass += 1
            lines.append(f"  [{i}] {t['action']:8} ✓")
        else:
            lines.append(f"  [{i}] {t['action']:8} ✗ {d.describe(max_cells=6)}")
    head = f"simmer test: {npass}/{len(trans)} transitions reproduced  ({path})"
    return head + ("\n" + "\n".join(lines) if lines else "")


def step_cmd(path, index: int, no_grid: bool) -> str:
    trans = _load(path)
    if not 0 <= index < len(trans):
        raise SystemExit(f"simmer: index {index} out of range (0-{len(trans)-1})")
    t = trans[index]
    before = np.asarray(t["before"], np.int16)
    after = np.asarray(t["after"], np.int16)
    pred = np.asarray(step(before, t["action"], t.get("x"), t.get("y")), np.int16)
    d = diff_grids(after, pred)
    verdict = "✓ reproduced" if d.changed == 0 else f"✗ {d.describe(max_cells=12)}"
    out = f"step [{index}] {t['action']} (x={t.get('x')}, y={t.get('y')}) → {verdict}"
    if not no_grid:
        out += "\npredicted grid:\n" + render_grid(pred)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="simmer", description="Functional sim engine — differential test vs piper.")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test", help="replay the corpus through step; report reproduced/missed")
    t.add_argument("--corpus", type=str, default=None)
    t.set_defaults(fn=lambda a: test(_corpus(a)))
    s = sub.add_parser("step", help="apply step to one transition; show prediction vs reality")
    s.add_argument("index", type=int)
    s.add_argument("--corpus", type=str, default=None)
    s.add_argument("--no-grid", action="store_true")
    s.set_defaults(fn=lambda a: step_cmd(_corpus(a), a.index, a.no_grid))
    return p


def _corpus(a):
    from pathlib import Path
    return Path(a.corpus) if a.corpus else CORPUS


def main() -> None:
    args = build_parser().parse_args()
    print(args.fn(args))


if __name__ == "__main__":
    main()
