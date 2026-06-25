"""Persisted game session so the agent-facing CLI tools are stateful across
separate process invocations.

Each `arcg` command is its own process. To keep one game going we persist, in a
JSON file under `.arc/`:
- the identifiers (`game_id`, `guid`, `card_id`),
- the latest grid (so `act` can diff against it and `look` can re-render),
- the AWSALB* cookies (session affinity — see client.ArcClient),
- a scratchpad of notes the agent jots for itself.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

STATE_DIR = Path(".arc")
STATE_FILE = STATE_DIR / "session.json"


@dataclass
class Session:
    game_id: str = ""
    guid: str | None = None
    card_id: str = ""
    state: str = "NOT_PLAYED"
    score: int = 0
    win_score: int | None = None
    step: int = 0
    available_actions: list[str] = field(default_factory=list)
    grid: list[list[int]] = field(default_factory=list)
    cookies: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = STATE_FILE) -> "Session":
        if not path.exists():
            raise FileNotFoundError(
                f"No active session ({path}). Run `arcg start <game>` first."
            )
        return cls(**json.loads(path.read_text()))

    @classmethod
    def load_or_none(cls, path: Path = STATE_FILE) -> "Session | None":
        return cls.load(path) if path.exists() else None

    def save(self, path: Path = STATE_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @staticmethod
    def clear(path: Path = STATE_FILE) -> None:
        path.unlink(missing_ok=True)
