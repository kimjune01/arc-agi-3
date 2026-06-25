"""Random baseline: pick uniformly among available actions.

This is the throwaway agent whose only job is to produce a *failing* verdict —
a connected, end-to-end run that loses. It establishes the floor everything
smarter has to beat.
"""

from __future__ import annotations

import random

from ..perception import Observation
from ..structs import Action, FrameData, GameAction
from .base import Agent


class RandomAgent(Agent):
    name = "random"

    def __init__(self, *args, seed: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(seed)

    def choose_action(self, obs: Observation, frame: FrameData) -> Action:
        choices = [a for a in frame.available_actions if a is not GameAction.RESET]
        if not choices:
            choices = [GameAction.ACTION1]
        kind = self._rng.choice(choices)
        if kind.is_complex:
            return Action(kind, x=self._rng.randint(0, 63), y=self._rng.randint(0, 63),
                          reasoning="random baseline")
        return Action(kind, reasoning="random baseline")
