"""Layer 3 — memory. The agent's scratchpad of findings."""

from __future__ import annotations

from . import store


def note(text: str) -> str:
    sess = store.load()
    sess.notes.append(text)
    store.save(sess)
    return f"noted ({len(sess.notes)} total)"


def notes() -> str:
    sess = store.load()
    if not sess.notes:
        return "(no notes)"
    return "\n".join(f"- {n}" for n in sess.notes)
