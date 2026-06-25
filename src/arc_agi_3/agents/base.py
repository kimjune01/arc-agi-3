"""Base agent: drives the RESET → observe → act loop and reports a verdict."""

from __future__ import annotations

from dataclasses import dataclass

from ..client import ArcClient
from ..perception import Observation, Perception
from ..structs import Action, FrameData, GameState


@dataclass
class Verdict:
    game_id: str
    guid: str | None
    state: GameState
    score: int
    win_score: int | None
    actions_taken: int

    @property
    def won(self) -> bool:
        return self.state is GameState.WIN

    def __str__(self) -> str:
        flag = "WIN" if self.won else "FAIL"
        target = self.win_score if self.win_score is not None else "?"
        return (
            f"[{flag}] {self.game_id}  state={self.state.value}  "
            f"score={self.score}/{target}  actions={self.actions_taken}"
        )


class Agent:
    """Subclass and implement `choose_action`."""

    name = "base"

    def __init__(self, client: ArcClient, *, max_actions: int = 200, on_observe=None):
        self.client = client
        self.max_actions = max_actions
        self.perception = Perception()
        # optional callback(Observation) -> None, e.g. to stream/log perception
        self.on_observe = on_observe

    def choose_action(self, obs: Observation, frame: FrameData) -> Action:
        """Policy seam. Receives the perceived observation; returns an action."""
        raise NotImplementedError

    def is_done(self, frame: FrameData) -> bool:
        return frame.is_terminal

    def play(self, *, game_id: str, card_id: str) -> Verdict:
        self.perception.reset()
        frame = self.client.reset(game_id=game_id, card_id=card_id)
        actions = 0
        while True:
            obs = self.perception.observe(frame)
            if self.on_observe:
                self.on_observe(obs)
            if self.is_done(frame) or actions >= self.max_actions:
                break
            action = self.choose_action(obs, frame)
            frame = self.client.act(action, game_id=game_id, guid=frame.guid, card_id=card_id)
            actions += 1
        return Verdict(
            game_id=game_id,
            guid=frame.guid,
            state=frame.state,
            score=frame.score,
            win_score=frame.win_score,
            actions_taken=actions,
        )
