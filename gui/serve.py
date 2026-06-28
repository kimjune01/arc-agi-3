#!/usr/bin/env python3
"""gui/serve.py — a tiny localhost viewer for watching the agent play.

Stdlib only (no deps, no build). Serves the static viewer (gui/) plus two JSON endpoints over the
SAME shared run dir the tools use (`ARCG_STATE_DIR`, default `.arc/`):

  GET /api/live    the current session grid — score, state, last action — refreshed as the agent
                   plays (the viewer polls this once a second for LIVE mode).
  GET /api/frames  the recorded corpus (transitions.jsonl) reconstructed into an ordered frame
                   list for REPLAY. Evicted transitions (grids compressed to hashes) carry no grid,
                   so they are skipped and counted in `note`.

Run:  uv run python gui/serve.py            # then open http://localhost:6969
      ARCG_STATE_DIR=checkpoints/ls20-firstpoint uv run python gui/serve.py   # a saved run
"""
from __future__ import annotations

import json
import os
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 6969
GUI_DIR = Path(__file__).resolve().parent
REPO_ROOT = GUI_DIR.parent
STATE_DIR = Path(os.environ.get("ARCG_STATE_DIR", REPO_ROOT / ".arc"))

# Claude Code stores each session's transcript under ~/.claude/projects/<cwd with / and . -> ->.
# The reason harness spawns its wake/sleep agents with cwd = the repo root, so their live transcripts
# land in this dir — tailing the newest one is "the context window of whichever agent is thinking".
_ENCODED = str(REPO_ROOT).replace("/", "-").replace(".", "-")
TRANSCRIPTS = Path.home() / ".claude" / "projects" / _ENCODED


def _read_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _parse_token(tok: str | None):
    """A history token is `ACTION2` or, for a click, `ACTION6:x,y` (piper's `_token_str`). Split it
    into (action, x, y) so the viewer can show the INPUT that caused the frame — direction or click."""
    if not tok:
        return None, None, None
    if ":" in tok:
        a, coord = tok.split(":", 1)
        try:
            x, y = (int(v) for v in coord.split(","))
        except ValueError:
            x, y = None, None
        return a, x, y
    return tok, None, None


def live() -> dict:
    """The current frame straight from the session substrate — what the agent is looking at now."""
    s = _read_json(STATE_DIR / "session.json") or {}
    hist = s.get("history") or []
    action, x, y = _parse_token(hist[-1] if hist else None)
    return {
        "game_id": s.get("game_id"),
        "grid": s.get("grid"),
        "prev_grid": s.get("prev_grid"),   # the frame BEFORE the last action — so the diff is ready on load
        "score": s.get("score"),
        "win_score": s.get("win_score"),
        "state": s.get("state"),
        "spent": s.get("actions_spent"),
        "action": action, "x": x, "y": y,
    }


def frames() -> dict:
    """Reconstruct an ordered replay from the corpus. A full row carries its grids; an evicted stub
    carries only hashes (grids compressed away by the sleep-prune) and is skipped. Frame 0 is the
    first full row's `before`; each later frame is a full row's `after`, labelled by its action."""
    corpus = STATE_DIR / "transitions.jsonl"
    sess = _read_json(STATE_DIR / "session.json") or {}
    win_score = sess.get("win_score")
    if not corpus.exists():
        return {"frames": [], "note": f"no corpus at {corpus}"}
    rows = [json.loads(l) for l in corpus.read_text().splitlines() if l.strip()]
    full = [r for r in rows if not isinstance(r.get("before"), str)]   # str before == evicted stub
    evicted = len(rows) - len(full)
    out: list[dict] = []
    if full:
        first = full[0]
        out.append({"grid": first["before"], "label": "initial", "action": None, "x": None,
                    "y": None, "score": first.get("score"), "spent": 0, "state": "NOT_FINISHED",
                    "game_id": first.get("game_id"), "win_score": win_score})
        for r in full:
            xy = "" if r.get("x") is None else f" ({r['x']},{r['y']})"
            out.append({"grid": r["after"], "label": f"{r['action']}{xy}", "action": r.get("action"),
                        "x": r.get("x"), "y": r.get("y"), "score": r.get("score"),
                        "spent": r.get("spent"), "state": "NOT_FINISHED",
                        "game_id": r.get("game_id"), "win_score": win_score})
    note = f"{len(full)} full frames replayed"
    if evicted:
        note += f"  ·  {evicted} evicted transition(s) skipped (grids compressed by the sleep-prune)"
    return {"frames": out, "note": note}


def agent(n: int = 50) -> dict:
    """Tail the newest agent transcript — the live context of the wake/sleep session running now (or
    the last one, if idle). Flattens each message to readable events: prose, thinking, the tool call
    (Bash command / description), and a truncated tool result. Prototype-simple: newest mtime wins."""
    files = sorted(TRANSCRIPTS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime) if TRANSCRIPTS.exists() else []
    if not files:
        return {"session": None, "events": [], "phase": None, "age": None}
    f = files[-1]
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    phase = None
    events: list[dict] = []
    for r in rows:
        c = (r.get("message") or {}).get("content")
        if not isinstance(c, list):
            continue
        for b in c:
            t = b.get("type")
            if t == "text" and b.get("text", "").strip():
                txt = b["text"].strip()
                if phase is None and "WAKE pass" in txt:
                    phase = "WAKE"
                elif phase is None and "SLEEP pass" in txt:
                    phase = "SLEEP"
                events.append({"kind": "text", "text": txt})
            elif t == "thinking" and b.get("thinking", "").strip():
                events.append({"kind": "thinking", "text": b["thinking"].strip()})
            elif t == "tool_use":
                inp = b.get("input") or {}
                summary = inp.get("command") or inp.get("description") or json.dumps(inp)[:300]
                events.append({"kind": "tool", "name": b.get("name"), "text": summary})
            elif t == "tool_result":
                tc = b.get("content")
                if isinstance(tc, list):
                    tc = "".join(x.get("text", "") for x in tc if isinstance(x, dict))
                events.append({"kind": "result", "text": (tc or "").strip()[:600]})
    # phase also lives in the spawning prompt (a 'user' role first message); catch it there too
    if phase is None:
        head = json.dumps(rows[:3])
        phase = "WAKE" if "WAKE pass" in head else ("SLEEP" if "SLEEP pass" in head else None)
    return {"session": f.stem[:8], "phase": phase,
            "age": round(time.time() - f.stat().st_mtime, 1), "events": events[-n:]}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(GUI_DIR), **k)

    def _json(self, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (stdlib casing)
        if self.path.startswith("/api/live"):
            return self._json(live())
        if self.path.startswith("/api/frames"):
            return self._json(frames())
        if self.path.startswith("/api/agent"):
            return self._json(agent())
        if self.path in ("/", ""):
            self.path = "/viewer.html"
        return super().do_GET()

    def log_message(self, *a):  # quiet — don't spam the terminal on every poll
        pass


def main() -> None:
    print(f"arc-agi-3 viewer · http://localhost:{PORT}  (state dir: {STATE_DIR})")
    print("  LIVE polls the session as the agent plays · REPLAY steps the recorded corpus")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
