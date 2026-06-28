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

_TERMINAL = ("WIN", "GAME_OVER", "NOT_STARTED")  # NOT_STARTED = run ended, awaiting RESET
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


def _next_primitive(conn, node, avail, counts, _seen=None):
    """Descend a goal-decomposition to the first RUNNABLE primitive action (an available action
    leaf), least-used among ties — a minimal route-follower for the exploit path. Returns the
    action token or None (the plan resolves to nothing runnable yet → fall back to exploring)."""
    _seen = _seen or set()
    if node is None or node.anchor in _seen:
        return None
    _seen.add(node.anchor)
    if node.is_leaf:
        return node.action if node.action in avail else None
    runnable = []
    for child in node.children:
        a = _next_primitive(conn, dagger.get(conn, child), avail, counts, _seen)
        if a:
            runnable.append(a)
    return min(runnable, key=lambda a: (counts.get(a, 0), a)) if runnable else None


def decide(sess, counts: dict, *, conn=None, goal: str = dagger.WIN, corpus=None) -> tuple[str, dict]:
    """Pick the next paid action and say WHY (the `info` dict: mode, and the node when exploiting).

    EXPLOIT vs EXPLORE is the pragmatist gate (belief-is-the-edge-of-knowing): committing a route is
    high-stakes, so the driver follows a goal-plan ONLY when it is `actionable` at COMMITTED stakes
    (witnessed enough) — a freshly-abduced, under-witnessed win-recipe is NOT blindly followed; the
    agent keeps EXPLORING (witnessing) until the recipe accrues confidence. Knowledge is derived at
    the decision, indexed by what's at risk; it is not a property the plan has merely by existing.

    EXPLORE policy (the floor, when no plan clears the bar): among actions simmer predicts will move
    the avatar on the COUNTER-MASKED state (so the counter ticking alone isn't read as a move),
    prefer one predicted to reach a NOVEL masked state, then least-used, then name. simmer may be
    wrong — the postgate surprise catches it and records it, so the policy self-corrects.
    """
    before = np.asarray(sess.grid, np.int16)
    avail0 = [a for a in (sess.available_actions or _DEFAULT_ACTIONS) if a != "ACTION6"]

    # EXPLOIT: a goal-plan that is witnessed enough to commit at COMMITTED stakes (the high-stakes
    # threshold for a route). Below the bar, fall through to EXPLORE — the spend that earns witnesses.
    if conn is not None:
        plan = dagger.plan(conn, goal)
        if isinstance(plan, dagger.Node) and dagger.actionable(plan, dagger.COMMITTED):
            a = _next_primitive(conn, plan, avail0, counts)
            if a is not None:
                return a, {"mode": "exploit", "node": plan.anchor, "sim_move": True}
    # EXPLORE (no plan cleared the bar): probe to witness. ACTION6 (click) needs a coordinate
    # target we don't choose yet — skip it in the skeleton.
    avail = avail0
    m = load_corpus(corpus or CORPUS)          # EpMem: detected move-counter + known masked states
    counter = m.counter
    here = state_hash(before, counter)

    def has_untried(h: str) -> bool:
        return any((h, a, None, None) not in m.edges for a in avail)

    def explore(action, sim_move):
        return action, {"mode": "explore", "node": None, "sim_move": sim_move}

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
        return explore(min(untried, key=rank), True)

    # 2) HERE is fully expanded — walk toward the nearest state that still has an untried action.
    nxt = _toward_frontier(m.edges, here, has_untried)
    if nxt is not None:
        return explore(nxt, True)

    # 3) Reachable graph exhausted under this action set — least-used fallback.
    return explore(min(avail, key=lambda a: (counts.get(a, 0), a)), False)


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
            action, info = decide(sess, counts, conn=conn, goal=goal)   # exploit if actionable, else explore
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
                "mode": info["mode"],                   # 'exploit' (followed an actionable plan) | 'explore'
                "sim_move": info.get("sim_move", False), "surprise": bool(verdict.get("surprise")),
                "score": sess.score, "spent": sess.actions_spent,
            })
    finally:
        l0.end()

    summary = {"steps": len(log), "spent": sess.actions_spent, "score": sess.score,
               "surprises": surprises, "state": sess.state, "goal": goal}
    return {"summary": summary, "log": log}
