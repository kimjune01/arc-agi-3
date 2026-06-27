"""Layer 3 — memory. The agent's DURABLE scratchpad of findings.

Unlike the per-game session (cleared on start/end), notes PERSIST across sessions and runs: they
are the agent's standing theory of the game, re-read on re-hydration. Stored as a plain markdown
file under the state dir, so a fresh reasoner session can `arcg notes` to recover context.
"""

from __future__ import annotations

from ..session import STATE_DIR

NOTES = STATE_DIR / "notes.md"


def _lines() -> list[str]:
    if not NOTES.exists():
        return []
    return [ln.strip() for ln in NOTES.read_text(encoding="utf-8").splitlines() if ln.strip()]


def note(text: str) -> str:
    NOTES.parent.mkdir(parents=True, exist_ok=True)
    with NOTES.open("a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    return f"noted ({len(_lines())} total, durable)"


def notes() -> str:
    lines = _lines()
    return "\n".join(f"- {n}" for n in lines) if lines else "(no notes)"
