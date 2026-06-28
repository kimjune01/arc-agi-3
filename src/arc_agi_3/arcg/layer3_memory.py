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


def forget(substring: str | None = None, *, all_: bool = False) -> str:
    """Prune the prose scratchpad — the consolidation (sleep) pass's REMEDIATION step. Removes notes
    that have been compressed into structure (the dagger DAG) or falsified, so the next forward pass
    re-hydrates from clean memory instead of an ever-growing pile. Touches ONLY the notes; the jotter
    trace (the grounded record) is permanent and never pruned here."""
    lines = _lines()
    if all_:
        NOTES.write_text("")
        return f"forgot all {len(lines)} note(s)"
    if not substring:
        raise SystemExit("arcg forget: give a substring to match, or --all")
    kept = [ln for ln in lines if substring.lower() not in ln.lower()]
    NOTES.write_text("\n".join(kept) + ("\n" if kept else ""))
    return f"forgot {len(lines) - len(kept)} note(s) matching {substring!r}; {len(kept)} kept"
