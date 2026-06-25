"""Trace emitter: append-only, one JSON event per line, stamped with ts."""

import json

import arc_agi_3.arcg.trace as trace


def test_emit_appends_jsonl(tmp_path, monkeypatch):
    f = tmp_path / "trace.jsonl"
    monkeypatch.setattr(trace, "TRACE_FILE", f)

    trace.emit({"tool": "arcg", "layer": 1, "cmd": "look", "ok": True})
    trace.emit({"tool": "arcg", "layer": 1, "cmd": "move", "ok": False, "error": "wall"})

    lines = f.read_text().splitlines()
    assert len(lines) == 2
    e0, e1 = json.loads(lines[0]), json.loads(lines[1])
    assert e0["cmd"] == "look" and e0["ok"] is True and "ts" in e0
    assert e1["ok"] is False and e1["error"] == "wall"


def test_append_only_never_rewrites(tmp_path, monkeypatch):
    f = tmp_path / "trace.jsonl"
    monkeypatch.setattr(trace, "TRACE_FILE", f)
    # Duplicate events are PRESERVED — the trace is not idempotent (unlike jotter).
    for _ in range(3):
        trace.emit({"tool": "arcg", "cmd": "diff", "ok": True})
    assert len(f.read_text().splitlines()) == 3
