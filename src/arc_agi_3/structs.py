"""Core data structures mirroring the ARC-AGI-3 game protocol.

The grid `frame` is a list of 2D integer arrays (one per visible layer; usually
length 1). Cell values are colour indices 0-15, the same palette as ARC-AGI-1/2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GameState(str, Enum):
    """Lifecycle of a single game session."""

    NOT_PLAYED = "NOT_PLAYED"
    NOT_FINISHED = "NOT_FINISHED"
    WIN = "WIN"
    GAME_OVER = "GAME_OVER"


class GameAction(Enum):
    """The fixed action space, keyed by the API's integer `action_input.id`.

    ACTION1-5 and ACTION7 are simple (no arguments). ACTION6 is a "complex"
    action carrying a board coordinate (x, y), each 0-63. RESET (id 0) starts a
    new session or restarts the current level/game. The API reports
    `available_actions` as a list of these integers.
    """

    RESET = 0
    ACTION1 = 1
    ACTION2 = 2
    ACTION3 = 3
    ACTION4 = 4
    ACTION5 = 5
    ACTION6 = 6  # complex: requires (x, y)
    ACTION7 = 7

    @property
    def path(self) -> str:
        """REST path segment, e.g. `/api/cmd/ACTION1` or `/api/cmd/RESET`."""
        return self.name

    @property
    def is_complex(self) -> bool:
        return self is GameAction.ACTION6

    @property
    def is_simple(self) -> bool:
        return self not in (GameAction.RESET, GameAction.ACTION6)


@dataclass
class Action:
    """A chosen action plus optional payload and human-readable reasoning."""

    kind: GameAction
    x: int | None = None
    y: int | None = None
    reasoning: str = ""

    def payload(self, *, game_id: str, guid: str | None, card_id: str | None) -> dict:
        body: dict = {"game_id": game_id}
        if guid is not None:
            body["guid"] = guid
        if card_id is not None:
            body["card_id"] = card_id
        if self.kind.is_complex:
            if self.x is None or self.y is None:
                raise ValueError("ACTION6 requires x and y coordinates")
            body["x"] = self.x
            body["y"] = self.y
        if self.reasoning:
            body["reasoning"] = {"note": self.reasoning}
        return body


@dataclass
class FrameData:
    """One observation returned by the API after RESET or an action."""

    game_id: str
    guid: str | None
    state: GameState
    frame: list[list[list[int]]] = field(default_factory=list)
    score: int = 0
    win_score: int | None = None
    available_actions: list[GameAction] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def grid(self) -> list[list[int]]:
        """The top visible layer, or an empty grid if none."""
        return self.frame[-1] if self.frame else []

    @property
    def is_terminal(self) -> bool:
        return self.state in (GameState.WIN, GameState.GAME_OVER)

    @classmethod
    def from_json(cls, data: dict) -> "FrameData":
        actions = []
        for a in data.get("available_actions", []) or []:
            # The API reports integer ids (e.g. [1, 2, 3, 4]); tolerate names too.
            try:
                actions.append(GameAction(a) if isinstance(a, int) else GameAction[a])
            except (KeyError, ValueError, TypeError):
                continue
        return cls(
            game_id=data.get("game_id", ""),
            guid=data.get("guid"),
            state=GameState(data.get("state", GameState.NOT_PLAYED.value)),
            frame=data.get("frame", []) or [],
            score=data.get("levels_completed", data.get("score", 0)) or 0,
            win_score=data.get("win_levels", data.get("win_score")),
            available_actions=actions,
            raw=data,
        )
