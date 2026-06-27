"""The serial loop, as importable functions (the CLI in cli.py is a thin wrapper over these).

`decide` and `run` are the shared surface: a programmatic policy imports them, the CLI calls the
same code. Nothing here is CLI-only.
"""

from __future__ import annotations

import numpy as np

from .. import dagger
from ..arcg import layer0_protocol as l0
from ..arcg import store
from ..jotter.cli import CORPUS
from ..jotter.graph import load as load_corpus
from ..jotter.graph import state_hash
from ..simmer.engine import MODELED
from ..simmer.engine import step as simmer_step

_TERMINAL = ("WIN", "GAME_OVER")
_DEFAULT_ACTIONS = ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]


def _predict(before: np.ndarray, action: str):
    """simmer's free prediction of the successor grid, or None when simmer has NO COVERAGE (an
    action it doesn't model, or a failure). None means 'uncharted — worth a real probe', which the
    caller must NOT confuse with a modeled no-op (a wall). simmer is untrustworthy by design."""
    if action not in MODELED:
        return None
    try:
        return np.asarray(simmer_step(before, action), np.int16)
    except Exception:
        return None


def _toward_frontier(edges: dict, cur: str, has_untried) -> str | None:
    """BFS over the known masked-state graph from `cur` to the nearest state that still has an
    untried action; return the FIRST action to head that way, or None if the graph is exhausted.
    This is what turns greedy-local novelty (which oscillates) into systematic exploration."""
    import collections
    adj: dict = {}
    for (hb, a, _x, _y), ha in edges.items():
        adj.setdefault(hb, []).append((a, ha))
    seen = {cur}
    q = collections.deque()
    for a, ha in adj.get(cur, []):
        if ha not in seen:
            seen.add(ha)
            q.append((ha, a))          # carry the first action taken from cur
    while q:
        state, first = q.popleft()
        if has_untried(state):
            return first
        for a, ha in adj.get(state, []):
            if ha not in seen:
                seen.add(ha)
                q.append((ha, first))
    return None


def decide(sess, counts: dict, *, corpus=None) -> tuple[str, bool]:
    """Pick the next paid action. Policy: among actions simmer predicts will move the avatar on the
    COUNTER-MASKED state (so the move-counter ticking alone doesn't read as a move — the confound
    that made an earlier version loop), prefer one predicted to reach a NOVEL masked state, then
    least-used, then name. Returns (action, simmer_had_a_real_move). simmer may be wrong — the
    postgate surprise catches that and records it, so the policy self-corrects as the corpus grows.

    TODO: when dagger.plan returns a real decomposition (not a Hole) and arbor names live
    hypotheses, decide should spend piper where the free rollout is untrustworthy along the PLAN,
    not just toward novelty. This is the exploration floor.
    """
    before = np.asarray(sess.grid, np.int16)
    # ACTION6 (click) needs a coordinate target we don't choose yet — skip it in the skeleton.
    avail = [a for a in (sess.available_actions or _DEFAULT_ACTIONS) if a != "ACTION6"]
    m = load_corpus(corpus or CORPUS)          # EpMem: detected move-counter + known masked states
    counter = m.counter
    here = state_hash(before, counter)

    def has_untried(h: str) -> bool:
        return any((h, a, None, None) not in m.edges for a in avail)

    # 1) Untried actions from HERE — expand the current state before wandering off.
    untried = [a for a in avail if (here, a, None, None) not in m.edges]
    if untried:
        def rank(a):
            p = _predict(before, a)
            if p is None:
                return (0, counts.get(a, 0), a)               # no coverage: probe the unknown first
            h = state_hash(p, counter)
            if h == here:
                return (3, counts.get(a, 0), a)               # predicted wall: try last
            return (1 if h not in m.states else 2, counts.get(a, 0), a)  # prefer predicted-novel
        return min(untried, key=rank), True

    # 2) HERE is fully expanded — walk toward the nearest state that still has an untried action.
    nxt = _toward_frontier(m.edges, here, has_untried)
    if nxt is not None:
        return nxt, True

    # 3) Reachable graph exhausted under this action set — least-used fallback.
    return min(avail, key=lambda a: (counts.get(a, 0), a)), False


def run(game: str, *, goal: str = "win game", budget: int = 25,
        max_steps: int | None = None, conn=None) -> dict:
    """Drive `game` through the gated loop until WIN/GAME_OVER, the budget cap, or max_steps.

    Importable: a policy calls this directly; the CLI is a thin wrapper. `conn` is the dagger
    store (defaults to the session graph.db; pass an in-memory store for tests). Returns
    {summary, log} — the corpus (jotter) and the graph (dagger) persist as the durable record.
    """
    l0.start(game, budget_cap=budget)
    conn = conn if conn is not None else dagger.connect()
    sess = store.load()
    dagger.init(conn, sess.available_actions)          # seed apex + real leaves for this game

    counts: dict = {}
    surprises = 0
    log: list[dict] = []
    try:
        while sess.state not in _TERMINAL:
            if sess.budget_cap is not None and sess.actions_spent >= sess.budget_cap:
                break
            if max_steps is not None and len(log) >= max_steps:
                break

            plan = dagger.plan(conn, goal)             # JIT: Holes early (no decomposition yet)
            action, sim_move = decide(sess, counts)
            before = np.asarray(sess.grid, np.int16)
            pred = _predict(before, action)
            ref = f"dagger:{action}"                    # the real leaf, seeded by init()

            # The gated commit: pregates (well-formed refs) fire pre-API, postgate reconciles
            # piper XOR simmer when a prediction exists.
            frame = l0.act(action, dagger=ref, arbor="arbor:#probe",
                           pred=pred.tolist() if pred is not None else None)
            sess = store.load()
            counts[action] = counts.get(action, 0) + 1
            verdict = frame.raw.get("postgate", {})
            if verdict.get("surprise"):
                surprises += 1
            log.append({
                "step": len(log) + 1, "action": action,
                "plan": type(plan).__name__,            # 'Hole' until a decomposition is cached
                "sim_move": sim_move, "surprise": bool(verdict.get("surprise")),
                "score": sess.score, "spent": sess.actions_spent,
            })
    finally:
        l0.end()

    summary = {"steps": len(log), "spent": sess.actions_spent, "score": sess.score,
               "surprises": surprises, "state": sess.state, "goal": goal}
    return {"summary": summary, "log": log}
