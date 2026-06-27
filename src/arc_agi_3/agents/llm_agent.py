"""LLM policy agent: Claude chooses each action from the perceived observation.

Perception (grid + delta + palette) goes in; a JSON action comes out. The agent
keeps a small scratchpad of Claude's own notes so it can accumulate a theory of
the game's mechanics across steps.
"""

from __future__ import annotations

import json
import random
import re

from ..perception import Observation
from ..policy_claude import ClaudeError, ask_claude
from ..structs import Action, FrameData, GameAction
from .base import Agent

SYSTEM = """You are playing ARC-AGI-3: an unknown 64x64 grid puzzle game. You are \
not told the rules; you learn them only by acting and watching what changes.

Each turn you receive: the grid (one hex char per cell, '.'=empty), a colour \
histogram, the available actions, and the DELTA from your previous action (the \
cells that changed). The delta is your strongest clue to what each action does \
and where your avatar is.

Goal: raise the score (levels_completed) and reach state WIN. Avoid wasting \
moves once you know what an action does.

Plan by decomposing the goal. Break "reach WIN" into smaller subgoals you can act \
toward (e.g. "reach the lock", "collect the token"). Hold at least TWO candidate \
subgoals or approaches at once, never just one, so a dead end has a fallback: pursue \
the most promising and switch when it stalls. Reuse a subgoal you already named \
instead of renaming it, so the same subgoal stays one thing across turns.

Respond with ONLY one line of JSON, no prose:
{"action": "ACTION1", "x": null, "y": null, "plan": "<2+ subgoals toward WIN; mark the one you are pursuing>", "note": "<one mechanic fact to remember>"}
- action must be one of the available actions.
- x and y are integers 0-63 ONLY for ACTION6 (a click/place); otherwise null.
- plan is your current decomposition: at least two subgoals, with the active one marked.
- note is a terse memory for your future self (e.g. "12-block=avatar, A1=right")."""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMAgent(Agent):
    name = "claude"

    def __init__(self, *args, model: str = "sonnet", scratch_keep: int = 8,
                 seed: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.scratch_keep = scratch_keep
        self._notes: list[str] = []
        self._plan = ""                       # the agent's current decomposition (>=2 subgoals)
        self._trace: list[dict] = []          # per-step (action, plan, note) — observe the plan
        self._rng = random.Random(seed)

    def _fallback(self, frame: FrameData) -> Action:
        choices = [a for a in frame.available_actions if a is not GameAction.RESET] \
            or [GameAction.ACTION1]
        kind = self._rng.choice(choices)
        if kind.is_complex:
            return Action(kind, x=self._rng.randint(0, 63), y=self._rng.randint(0, 63),
                          reasoning="fallback")
        return Action(kind, reasoning="fallback")

    def _parse(self, text: str, frame: FrameData) -> Action:
        m = _JSON_RE.search(text)
        if not m:
            return self._fallback(frame)
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return self._fallback(frame)
        if note := obj.get("note"):
            self._notes.append(str(note)[:200])
        if plan := obj.get("plan"):
            self._plan = str(plan)[:400]      # prompt-level suggestion; empty if the agent ignores it
        try:
            kind = GameAction[obj["action"]]
        except (KeyError, TypeError):
            return self._fallback(frame)
        if kind not in frame.available_actions:
            return self._fallback(frame)
        if kind.is_complex:
            x, y = obj.get("x"), obj.get("y")
            if not (isinstance(x, int) and isinstance(y, int) and 0 <= x <= 63 and 0 <= y <= 63):
                return self._fallback(frame)
            return Action(kind, x=x, y=y, reasoning=str(obj.get("note", "")))
        return Action(kind, reasoning=str(obj.get("note", "")))

    def choose_action(self, obs: Observation, frame: FrameData) -> Action:
        scratch = "\n".join(f"- {n}" for n in self._notes[-self.scratch_keep:])
        prompt = (
            (f"Your notes so far:\n{scratch}\n\n" if scratch else "")
            + (f"Your current plan:\n{self._plan}\n\n" if self._plan else "")
            + obs.to_prompt(include_grid=True)
            + "\n\nChoose the next action. Update your plan if a subgoal is done or stalls. JSON only."
        )
        try:
            text = ask_claude(prompt, system=SYSTEM, model=self.model)
            action = self._parse(text, frame)
        except ClaudeError:
            action = self._fallback(frame)
        self._trace.append({"step": len(self._trace) + 1, "action": action.kind.name,
                            "plan": self._plan, "note": action.reasoning})
        return action
