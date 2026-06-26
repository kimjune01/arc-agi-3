# Worklog

Rotated 2026-06-25 at 1184 lines → earlier history in [WORKLOG.1.md](WORKLOG.1.md).
The snapshot below carries the standing state forward; append new entries under it.

## Current state (2026-06-25)

**Project.** Agent that plays ARC-AGI-3 (interactive grid games, rules learned by acting).
Architecture: five module CLIs (piper/simmer/jotter/arbor/dagger) + **Claude Code as the
driver** (the reasoner; modules are the harness). Governing rule is the **ratchet**: do it
in-head, watch where it breaks, codify only that. Plan in `PLAN.md`.

**Built (38 tests pass).**
- **piper** ← the layered `arcg` CLI: protocol/intent/state/memory layers; live on LS20.
  Adds `objects` (connected-component perception), a transition corpus
  (`transitions.jsonl`, budget-stamped), the append-only `trace.jsonl` (observability,
  opposite integrity class from jotter), and env-overridable state dir (`ARCG_STATE_DIR`,
  default `.arc` → use `/tmp/...` per run).
- **simmer** ← hand-edited pure `step(grid,action)` engine + `simmer test` (differential
  replay vs the corpus, localizes divergence). Editing the engine directly is INTENTIONAL
  (the agent IS the compiler; the differential test gives the safety a DSL would). Reproduces
  LS20 moves 4/4 after one refine cycle.
- **jotter** ← content-addressed state graph over the corpus (`state_hash`, dedup,
  transpositions) + `audit` (reconciles vs piper via gapless budget stamps; survives session
  end). Pairs with simmer for never-re-query (`has` = known/novel).

**Deferred (ratchet).** arbor (abductor port: abduce/kill/witness/from-kill), dagger (action
DAG); jotter's git substrate + branches/merge + belief/action provenance + commit motive-refs;
automated arbor→simmer compile (the agent hand-edits instead). Each lands when the in-head
version visibly breaks.

**Demo status.** M0 works live: piper + Claude-Code-driver on LS20. Determinism verified
(snapshot→restore→same act→identical ✓). Cold-start sequence holds (goal-guess first, then
goal-biased probe, then first mechanic). LS20 mechanic learned: ACTION1-4 slide the
12-avatar + 9-tail by 5, wall-blocked, energy bar (11) depletes per move.

**Key decisions/invariants** (detail in PLAN.md + WORKLOG.1.md):
- piper/simmer: identical *operative interface*, different *contract* (cost/exactness).
- idempotence test is non-trivial: `f ≠ I ∧ f∘f = f` (delimits the law; piper act fails it).
- two-root planner: win-down = abduction (goals, score-gated), act-up = deduction (mechanics,
  free in simmer); the plan is where they meet; arbor is the shared alphabet.
- uberty→security is a scheduled flow (budget regulates; surprise re-injects uberty), not a
  balance to strike.
- poka-yoke two layers: invariants + instructive errors (harness, pre-API/free), surprise
  engine (epistemic). Guard invariants, never hypotheses.
- iteration invariant (don't-backstep): each turn advances a monotone measure; budget-bearing
  backstep is structurally bounded (piper only on corpus-growing transitions).
- jotter commit message = a deterministic pointer into arbor/dagger (write-once makes it sound).

**Run conventions.** `uv run --project /Users/junekim/Documents/arc-agi-3 <arcg|simmer|jotter>`;
set `ARCG_STATE_DIR=/tmp/arcg-<run>` per run. Do NOT `cd` into the repo (autoenv prompt hangs
the shell) — use `git -C` and `--project`/absolute paths.

---

## 2026-06-25 — explainer prompt + fresh-instance drive (closes M0 step 2)

Wrote the two missing M0 pieces and validated them on a fresh LS20.

- **`bin/claim-run.sh [N]`** — optional run-number param → claims `/tmp/arcg-run<N>`.
  Given N: idempotent (re-claim resumes the same dir). Omitted: picks next free number
  so a new run never collides. Prints only the dir on stdout (captureable as `RUN=$(...)`);
  narration on stderr; validates the arg. All three modules share `ARCG_STATE_DIR=$RUN`.
- **`EXPLAINER.md`** — the session opener (M0 step 2). The MAP not the manual: run-dir
  claim, goal, the serial loop, tool→role (piper/simmer/jotter), the three principles
  (determinism/budget/figure-ground), the cold-start start sequence. Defers every *how*
  to `--help` + AGENT.md. This is what makes the demo run from a FRESH session, not just
  the one that built it — the gap that left M0 unclosed.

**Drive (run1, fresh LS20 instance, budget 3/40).** Cold-start sequence ran as written:
`look`+`objects` → goal-guess note → goal-biased probe. Findings:
- ACTION1 = up: slides the 12-avatar + 9-tail unit by 5, wall-blocked. ACTION3 here =
  blocked (avatar pinned by wall, only the bar moved).
- 11-bar = an **on-board move counter**: 1 column (2 cells) depletes per action, ~42 total.
- **The mechanic model TRANSFERRED to a fresh instance with zero divergence**: simmer
  reproduced 3/3 (incl. the new action and the blocked move); jotter `audit` MATCH ✓
  (gapless stamps, count == piper actions_spent).

**Ratchet read.** Nothing in-head broke. piper/simmer/jotter are solid on a fresh board;
the perception/mechanic/memory stack generalizes. The unsolved frontier is the **GOAL
side** — score stayed 0/7, straight navigation doesn't score, win condition unknown. So
the next module-break will come from win-down/goal decomposition (dagger / arbor's
goal-claims), not from perception or mechanics. Confirmed by driving, not guessed: arbor
and dagger stay ratchet-deferred until a real run-to-score taxes the in-head goal model.

## 2026-06-25 — templated-prior idea: energy-bar premise tested + falsified (free peek)

Floated: if the energy bar recurs in every game, provide it as a templated module.
Tested the premise with free `objects` peeks at ft09/vc33/cd82 (0 budget). Result:
- ft09, cd82: **no colour-11, no bar.** vc33: colour 11 present but as small vertical
  blocks (6×2, 4×2), **not** a bottom strip — 11 means a different object there.
- **Colour is not a stable cross-game key**: background runs 4/5/3 across these games;
  11 = energy bar in LS20 but tokens in vc33. A colour-keyed template would mis-fire.
- **The universal abstraction we already have**: every game has a move limit, and piper
  already meters it (`actions_spent`/budget cap). The LS20 11-bar is just an on-board
  *rendering* of that counter — redundant with piper. Nothing to template.

Decision: no energy-bar module. The bestiary idea (recurring primitives →
`(recognizer, default-mechanic, default-role)` seeded as KILLABLE defaults to cheapen
cold-start — pre-loaded uberty, hypothesis side per the poka-yoke boundary) is sound,
but must key on STRUCTURE/geometry not colour, and the trigger is re-deriving the same
structural primitive in a 2nd game. n=1 on every primitive so far; deferred.

## 2026-06-25 — observed subagent drive (scored 1/7) + simmer passability refinement

Ran a FRESH general-purpose subagent as the driver (no context inheritance), caught up
only by EXPLAINER.md, on LS20. Watched it via its run's trace, not its play-by-play.

**Drive result (run2).** Scored 1/7 in 17/30 actions. It discovered the full LS20 loop:
slide avatar+tail by 5 (ACTION1-4 = up/down/left/right); collect the token (0/1) to
toggle a carried-pattern HUD toward a lock target (3x3 of 9s); overlap the lock → +1 and
the level regenerates. It only won after scripting an inline engine-backed BFS over the
5-cell lattice — hand-planning a ~17-move route in ASCII broke.

**Observability validated.** Reconciled its self-report against the OBJECTIVE record it
can't fake: `trace.jsonl` (17 moves = 17 budget, 0 errors), `jotter audit` (stamps 1..17
gapless), and `simmer test` (13/17). Its "where I broke" claim mapped 1:1 to the 4
simmer-test failures, cell counts matching (60/5/50/1469). It left NO tracked-file edits
and NO scripts (the BFS was ephemeral). Driver's subjective report == ground-truth trace.
This is the design's central observability claim, validated on a real run. (Null worth
recording: 0 transpositions / 0 revisits — jotter's dedup earned nothing this forward-only
run.)

**simmer refinement (the agent-IS-compiler loop, licensed by the 4 misses).** Studied the
3 fixable transitions: the avatar was witnessed sliding through box-wall (5) and token
(0/1) cells the "corridor-only" rule called blocking. Widened `_slide` passability:
`PASSABLE = {3, 0, 1, 5}` (witnessed-only; 4 still blocks, 11 not asserted). Result
13→14/17, run1 still 3/3, 38 tests pass. Remaining misses are the two DEFERRED classes,
both reachability-irrelevant: the collected-token HUD repaint (`[9]` now just 10 cells of
HUD churn, `[10]` 5 cells) and the level-regen (`[16]`, a goal-event boundary the engine
shouldn't model). Modelled reachability (what a planner needs), not collectible state.

**Next break named: dagger.** The subagent had to improvise a planner to win one level;
the collect→match→deposit loop ×7 is a clean fixed decomposition, and the bottleneck is
path-length vs budget (level 2's token/lock were each ~17 moves off). That's the in-head
planner visibly breaking — the ratchet trigger for dagger. arbor still not forced (few
claims, held fine in notes/head).

## 2026-06-25 — dagger typed loosely (DAGGER.md), the composition invariant

Wrote `DAGGER.md`: dagger's soft-typing pass (prose, no type system; formal typing
deferred until prose goes off the rails, per standing call). Combined Winston (6.034 goal
trees / problem reduction; "the right representation exposes the constraint") with the
monoidal-contract composition insight to land the ONE invariant:

- **node = morphism** (perspectival: goal-from-above = postcondition/codomain,
  action-from-below = state transformation). The blog's "every node is a goal from above
  and an action from below" *is* an arrow.
- **decomposition = commuting factorization**: `compose(children) ⊨ parent`. Decompose and
  compose are inverse; exhaustiveness is round-trip fidelity; a lossy decomposition is a
  diagram that doesn't commute. `compose` = action monoid (sequence, ordered) or
  meet-semilattice (conjunction, the merge law).
- **composition = codomain-meets-domain**: `A;B` iff `post(A) ⊨ pre(B)` — the categorical
  composability condition, which is exactly pre/post matching.
- pre/post are PROSE, `⊨` is judged (LLM, sharpened by simmer), the invariant is TESTED by
  running children in simmer and checking the parent predicate fires — the non-commutation
  names the missing child (`from-kill`). Two roots meet at the commuting square.

Grounded in the observed LS20 loop: `deposit = collect-token ; route-to lock ; overlap-lock`,
`route-to` the shared sub-action, ×7 = the win. Deferred: DSL, subsumption engine, proving
(vs testing) the invariant, object-identity, minimality.

## 2026-06-25 — dagger typing tried on a drive (run3) + drop-in research (codex)

**Observed drive planning in the dagger frame (run3).** Fresh subagent, read DAGGER.md as
its planner. Scored 1/7 (30 budget; level-2 was budget-locked at a 37-move optimum with 27
left — unwinnable, not a frame failure). The typing EARNED ITS KEEP: on level 2 the driver
deliberately omitted `collect-token`, achieved `route-to-lock ; overlap-lock`, and the
parent predicate (`score += 1`) did NOT fire. The diagram failed to commute; the residual
localized to `overlap-lock`'s precond "carried matches lock" = false; the gap **correctly
named the missing child = collect-token**. Exactly the catch-and-name-the-repair the
commuting-factorization invariant was built for.

**Typing limit surfaced (first hardening candidate).** `compose(children) ⊨ parent` is only
FREE when a postcondition is a reachability predicate (simmer-checkable). For a
collectible-STATE postcondition ("carried matches lock", a HUD predicate simmer can't see),
the check degrades to "verify in piper" (costs budget). Cheap fix WHEN IT RECURS: a one-bit
annotation per pre/post — `reachability-checkable` vs `state-checkable` — so the planner
knows in advance which entailments are free vs budget-bearing. Not built (ratchet).

**Reconciliation caught a driver blind spot (observability working).** Driver claimed "no
new mispredicts" — true for avatar reachability (its routes landed as simmer predicted), but
`simmer test` on the full corpus is 10/30: 20 misses are ONE bug — after a level-regen the
new level has a SECOND colour-11 object (vertical segment rows 16-18 col 15), so
`_deplete_bar` (remove leftmost 11-column) depletes the wrong region every post-regen move.
Reachability-irrelevant (avatar unaffected, drive unharmed), so the self-report missed it;
the objective trace did not. Deferred engine note: the bar model is single-bottom-bar-only;
the bar is redundant with piper's budget anyway, so fixing it is low-value.

**Drop-in research (codex). No usable implementation of the full compound exists** (persistent
similarity-indexed HTN/DAG + LLM-JIT decomposition on miss + write-back + self-healing +
primitive-API leaves). High confidence. Best build path BANKED for when prose dagger breaks:
- **GTPyhop** (Dana Nau, BSD, actively packaged on PyPI) = the HTN/goal-task recursive
  resolver; already supports mixed tasks/goals with Python-function operators + leaves.
- **Voyager `SkillManager`** (MIT; Chroma + embedding retrieval + write-only-after-success)
  = the persistent similarity-indexed layer; swap "skill = JS code" → "node = {intent, pre,
  post, mode, children, primitive?}".
- **ChatHTN verifier-tasks** (Muñoz-Avila et al., Apache-2.0, built on PyHop) = donor for the
  `compose(children) ⊨ parent` check.
Honest size: fork-and-extend, ~few hundred lines (node store + resolver + GTPyhop adapters),
NOT drop-in. Build only when prose dagger (DAGGER.md) visibly goes off the rails — it didn't
this run.
