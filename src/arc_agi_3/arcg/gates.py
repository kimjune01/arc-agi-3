"""Pregates and the postgate — runtime enforcers of the act/commit contract.

A gate makes a condition hold at the action boundary, or refuses. Pregates fire
PRE-API (zero budget — a malformed action never reaches the game); the postgate fires
POST-act (after the real frame lands). Each gate has exactly three exits:

  hold   -> proceed (returns the normalized ref / verdict).
  bounce -> a KNOWN violation: raise UsageError, tool-prefixed, naming the rule AND the
            recovery. Zero budget. The driver learns the contract by hitting it.
  crash  -> the UNANTICIPATED: let a non-UsageError propagate uncaught (the andon cord).
            Crash is the default; only known violations become bounces.

These guard PROCESS invariants (HOW the driver acts — refs present, hypothesis named,
facts consulted), never game hypotheses (WHAT the rules are). A wrong game-belief is a
postgate witness/kill, never a crash.

Reality note: `arbor` (hygraph) and `dagger` (action-DAG) are not built yet — there is no
node registry to check liveness against. So the pregates check WELL-FORMEDNESS only; the
liveness checks are TODOs that land when those modules do. Enforcing liveness now would
guard a hypothesis against state that doesn't exist.
"""

from __future__ import annotations


class UsageError(RuntimeError):
    """A known precondition violation: instructive, expected, zero-budget. Tool-prefixed,
    names the rule + recovery. NOT a bare assert (python -O strips asserts; gates are
    load-bearing contract, not debug scaffolding)."""


DAGGER_PREFIX = "dagger:"
ARBOR_PREFIX = "arbor:#"


def dagger_gate(ref: str | None) -> str:
    """Pregate: the action must name the plan/action node it executes (`dagger:<id>`).

    Process invariant — *that* the driver names its plan step, never *what* the game is.
    TODO: wire liveness. The reader now exists (`dagger.get(dag, ref)` -> `dagger.live(node)`);
    what's missing is WHERE the Dag lives so the act path can reach it (session/store) and the
    driver passing real node ids from `dagger.plan()` instead of the placeholder dagger:intent:*
    refs the convenience wrappers pass. Note `dagger.live` only checks not-killed; full liveness
    = REACHABILITY in the dag, a matcher-judged property (B's postcond ⊨ A's precond is
    generalize-or-specialize, tolerant), not a registry ==. Well-formedness only here for now.
    """
    if ref is None:
        raise UsageError(
            "dagger-gate: action names no plan node — pass dagger:<id>, the action-DAG "
            "node it executes (dagger:probe for an undirected move)")
    if not isinstance(ref, str):
        raise TypeError(f"dagger-gate: plan-node ref must be str, got {type(ref).__name__}")
    node = ref.strip()
    if not node.startswith(DAGGER_PREFIX) or not node[len(DAGGER_PREFIX):].strip():
        raise UsageError(
            f"dagger-gate: malformed plan-node ref {ref!r} — expected dagger:<id> with a "
            "non-empty id")
    return node


def arbor_gate(ref: str | None) -> str:
    """Pregate: the action must name a live hypothesis it tests (`arbor:#<id>`); a blind
    probe still names an OPEN node (`arbor:#<open>`) — every action tests *something*.

    TODO: require a prediction alongside the ref, and check the node is open/not-killed
    once `arbor` (the hygraph) exists (no graph yet -> well-formedness only).
    """
    if ref is None:
        raise UsageError(
            "arbor-gate: action names no hypothesis — pass arbor:#<id>, the claim it tests "
            "(arbor:#<open> for a blind probe)")
    if not isinstance(ref, str):
        raise TypeError(f"arbor-gate: hypothesis ref must be str, got {type(ref).__name__}")
    node = ref.strip()
    if not node.startswith(ARBOR_PREFIX) or not node[len(ARBOR_PREFIX):].strip():
        raise UsageError(
            f"arbor-gate: malformed hypothesis ref {ref!r} — expected arbor:#<id> with a "
            "non-empty id")
    return node


def jotter_gate(plan_actions, effects: dict) -> list:
    """Pregate (plan-time): a plan is vetted against grounded facts (`jotter effects`)
    before it runs — the run13 energy-budget miss, as a gate. Every action the plan leans
    on must appear in the grounded effects, so the plan can't assume an effect reality
    never demonstrated.

    NOTE ON ROUTING: this gate's home is the PLANNING seam (`dagger.plan`), NOT the
    per-act commit — a novel action legitimately isn't in `effects` yet (you spend an
    action to GROW the corpus), so gating it per-act would block exploration. `dagger.plan`
    isn't built, so this ships define+test with routing DEFERRED. TODO: route at
    `dagger.plan` once it exists.
    """
    if plan_actions is None:
        raise UsageError("jotter-gate: no plan to vet — pass the plan's action list")
    if not isinstance(effects, dict):
        raise TypeError(f"jotter-gate: effects must be a dict, got {type(effects).__name__}")
    ungrounded = [a for a in plan_actions if a not in effects]
    if ungrounded:
        raise UsageError(
            f"jotter-gate: plan leans on ungrounded actions {ungrounded} — run "
            "`jotter effects` and confirm each action's effect before planning on it")
    return list(plan_actions)


def postgate(pred_grid, real_grid) -> dict:
    """Postgate (post-act): reconcile piper ⊕ simmer. Records a witness (sim matched
    reality) or a kill (sim mispredicted — surprise). The surprise engine made mechanical.

    Precondition the pregates lack: a simmer prediction must EXIST to reconcile against,
    so the caller fires it only when one does — calling with None is a caller-contract
    breach (a crash, not a bounce).

    A mispredict is a KILL (a wrong hypothesis), never a crash: crash is for process
    failure, not a wrong belief.

    TODO: localize the diff bbox and feed a kill -> `arbor.from_kill` once arbor exists.
    """
    if pred_grid is None or real_grid is None:
        raise TypeError(
            "postgate: needs both pred and real grids (the caller must confirm a simmer "
            "prediction exists before firing)")
    surprise = pred_grid != real_grid
    return {"surprise": surprise, "verdict": "kill" if surprise else "witness"}
