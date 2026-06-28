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

## 2026-06-25 — DAGGER.md: uncertainty, champion/challenger, e-values

Extended DAGGER.md's soft typing with how uncertainty is handled (all prose, no machinery):
- **Express uncertainty as status + the trial that settles it, never a probability.** Each
  uncertain element carries: conjecture-marked prose; a security status (untested → witnessed×N
  → killed, arbor's vocabulary, credence by set-add-of-trials not `++`); and the discriminating
  trial + cost class (free=simmer/reachability, paid=piper/state, unmodellable). Forcing
  function: no nameable trial → not a usable hypothesis. The annotation IS the node's
  uberty→security position.
- **Why not champion/challenger A/B (June's prior impl, "rather expensive").** It pays to
  evaluate challengers speculatively; expensive for 3 reasons this setting removes —
  nondeterminism→statistics (here deterministic→n=1 kill), expensive feedback→real runs (here
  simmer→free comparison), no simulator (here simmer IS it). dagger keeps ONE champion, runs
  only it, surprise nominates the challenger (from-kill, strictly dominating, gated free vs the
  corpus). Survives only as a rare paid probe for a state-effect a long plan depends on.
- **The Boolean kill is a degenerate e-value test** (June's prior used e-values vs champion-as-
  null with implicit hill-climbing). A deterministic champion assigns prob 1, so one mispredict
  sends the test martingale to ∞ at n=1 — anytime-validity for free, threshold irrelevant.
  e-values genuinely earn their keep only on the sparse/paid GOAL layer (score many-to-one,
  delayed), where optional stopping promotes a goal-decomposition on the fewest paid actions.
  Surprise-driven climb beats perturbation hill-climb: ∞-size steps where deterministic, and
  counterexample-generated (not perturbation-generated) challengers escape local optima.
  Banked for arbor (witness/credence ledger) when prose status can't discriminate; not built.

## 2026-06-25 — terminology fix: uberty ⊥ cost (per reading/methodeutics ch2)

Caught a conflation (mine, in conversation; one spot in PLAN.md): I'd been using **uberty**
to mean "free/cheap/unbounded," collapsing the cost axis into the uberty/security axis. Per
Peirce (1913) / methodeutics ch2: **uberty = how much a conclusion exceeds its premises**
(information gain); **security = whether it can be false given true premises**. Both are
properties of the inference *mode*, independent of compute cost. Corrected mapping:
- abduction = max uberty / min security — propose a mechanic or decomposition — **free**.
- deduction = zero uberty / max security — simmer rollouts (apply the learned step) — **free**.
- induction = moderate both — **piper**: witness prediction vs reality, grow the corpus — **paid**.
Cost is a separate column: abduction AND deduction are both free (imagination); only induction
is metered. So "uberty is free (simmer)" was wrong twice — simmer is *deduction* (not the
uberty source), and freeness isn't what makes a mode uberty. Fixed PLAN.md §uberty-vs-security
(budget regulates the inductive conversion, not the poles). DAGGER.md was already clean (uberty
= node status; cost = the trial's separate free/paid class). Bench upshot, restated correctly:
ARC-AGI-3 meters *induction* and leaves abduction+deduction free — sample-efficiency is
inductive-efficiency (fewest witnesses to ground a model free deduction can then run on).

## 2026-06-25 — deep drive (run4) + jotter canonical hash (revisit blindness fixed)

**Deep drive, budget 100 (run4).** Scored 1/7, stopped at a real budget-lock on level 2.
Watched it LIVE via the game trace (not the subagent transcript) and reconciled after.
- **Mystery the live trace posed, the drive solved.** Trace showed the avatar stuck in an
  18-cell box, cell (35,29) hit 11x — looked like aimless thrashing. It wasn't: the energy
  bar is not a soft counter, it **resets the avatar to level-start, refills the bar, and
  spends one of 3 lives** (colour-8 counter 12→8→4) when it depletes (~21 moves/life). The
  "circling" was repeated forced resets to start. The trace localized the symptom; active
  play found the mechanism.
- **11 is an ENERGY PICKUP, not a wall.** Maze 11-clusters refill the bar on overlap (no life
  lost). simmer had 11 as wall, so every BFS route avoided them → level 2 looked infeasible.
  The drive hand-edited `engine.py` PASSABLE += 11 (witnessed; run1 still 3/3, 38 tests pass,
  0 avatar-position regressions — verified independently). This IS a piper⊕simmer surprise
  (predict blocked, reality moved+refilled), abduced and compiled by hand — the abductor loop.
- **Goal-layer answer to "is it using mechanical XOR":** for the MECHANIC layer yes (the
  11-pickup was a reachability surprise the XOR catches). For the RESOURCE constraint the XOR
  is structurally SILENT — simmer predicted every avatar position correctly, so piper⊕simmer=0
  across all 62 stuck moves; the reset/lives mechanic cost ~20 paid piper actions to reverse-
  engineer. The mechanic layer has a detector; the goal layer has none.
- **Prose dagger held** — every uncertainty was a Boolean kill, no e-value/credence needed
  (e-value layer stays banked). The real off-rails signal is SCOPE: dagger types per-node
  pre/post but has no slot for a whole-SEQUENCE resource budget (route-length vs energy). That
  is the next typing question — a resource gate on a composite (monoid-sum of step costs ≤
  budget), distinct from pre/post matching. Drive's build-next: (1) resource-budget child on
  the route node + pickups as mandatory waypoints when route_len > bar, (2) model bar/lives in
  simmer, (3) approach-rotation operator on the deposit predicate (HUD match is rotation-
  dependent on approach direction).

**jotter canonical hash (fixes the revisit blindness this drive exposed).** The state hash was
over the raw grid, so the monotone bar made every state unique → `revisits/transpositions`
could never fire (jotter was blind to the very thrashing above; confirmed live: same avatar
cell → 3 distinct hashes). Fix: `state_hash` now hashes a CANONICAL grid — mask the bar's whole
row band (the bar is the bottommost 11-component; include corridor-3 since depleted columns
read as corridor; mask the colour-8 lives counter in that band too so a reset matches level-
start). Pickups (small 11, higher up) kept as salient. Payoff: run4 79→39 unique states,
0→18 revisits, 0→2 transpositions; runs 1–3 surfaced 1–2 hidden reconvergences; 38→40 tests.
The ~20 actions the drive spent reverse-engineering the reset would have been a free "I'm back
at level-start" revisit signal with this in place — induction made cheap by better content-
addressing. LS20-specific by design (widen at game 2).

## 2026-06-25 — the resource gate is a graded(-Elgot) monad (GRADES.md)

Design thread (codex consult + the LP-smell instinct) converged on the right shape for the
run4 resource constraint, then on its theory. New `GRADES.md` captures it; DAGGER.md gets the
implementation subsection (A* admissibility witness) + a pointer.
- The energy gate is a **grade**, not an LP constraint: cost monoid `(ℕ∪{∞},+,0)`, grades
  COMPOSE (monoid action) rather than being solved. Implement as **A\*** over
  `(cell, energy, lives, carried)`, `h`=lattice distance, node identity = jotter's canonical
  hash; simmer stays pure geometry; `EnergyClaim` is the witnessed grading; driver gates piper
  spend; infeasible decomposition → `from-kill`. A* = least-grade morphism in the graded
  monad's Kleisli category. codex's verdict (don't put energy in simmer; admissibility witness
  in dagger; resource-constrained-path not PDDL) holds; the LP smell was real and correctly
  routed us to search-not-solve.
- Reset = graded **Elgot** dagger (June's `graded_elgot_in_python.py`), but BOUNDED by a
  well-founded fuel (lives ≤3, energy ~21/leg) → we sit in the draft's Layer 2 (known `k`),
  never the Layer-3 closure gap (`star_additive(m)=∞`, the unpublished graded dagger).
- **The payoff identification**: Layer 2 (bounded, finite static grade) vs Layer 3 (unbounded,
  `m*=∞`) IS the deduction/induction = free/paid line. So the graded-Elgot gap is the
  categorical signature of the `unmodellable` cost-class in DAGGER.md — a trial whose grade is
  statically undefined, resolvable only by paid induction. Justifies `unmodellable` as a real
  third class, not a hedge.
- Typing home = graded Hoare (`reading/.../hoare-graded`); lattice-collapse soundness = Markov
  / path-independence (Fritz-Perrone). lattice + graded + content-addressed dedup = one object:
  a cost-graded deterministic (Markov) reachability monad. Nothing built yet — theory pinned.

## 2026-06-25 — graded theory DEBUNKED and removed; "it's DP"

Two codex reviews (what-to-do, then design-review) plus June's own deflation ("is it DP?")
collapsed the graded(-Elgot) theory:
- The central identification `m* = ∞ ⟺ must-witness` is **unsound** — metaphor, not math.
  `m* = ∞` is a conservative static upper bound under a grade-only abstraction, NOT epistemic
  unknowability. Counterexample: `countdown(n)` is bounded yet grade-unbounded → deducible as
  `n·m` with a ranking function, no witnessing. The free/paid line is *finite certificate vs
  no certificate under the current abstraction*, with three escapes (refine / rank / witness),
  not finite-vs-infinite behaviour.
- The engine was always just **DP**: resource-constrained shortest-path over augmented state,
  grade = the DP value (tropical (min,+) semiring), reconverging lattice = overlapping
  subproblems. The CT earned exactly two things and nothing more: it ruled out LP, and it
  located the certificate/termination question codex then made precise.
- Design review also killed two committed errors: "node identity = jotter's canonical hash"
  (it's ONE coordinate, not the state — one canonical state with NAMED projections) and
  putting `V/π` in jotter (category error — that's procedural/dagger, not episodic). And
  `EnergyClaim` → `RouteModelClaim` (model wrongness is broader than energy). Memoization
  recast as lazy caching of *executed* successful suffixes with stepwise prefix-verification,
  conjectural-until-verified; no full value table, no "optimal" claim over an unproven-Markov
  abstraction.

Action: **removed GRADES.md** (the debunked theory note); rewrote DAGGER.md's resource section
to the sound DP version (no graded apparatus, no GRADES.md pointer). Kept only the deflated
takeaway: it's DP; admissibility = resource-constrained shortest-path; certificate = finite
cost bound ≤ budget.

Next direction (not built; codex-reviewed). Hypothesis generator = **object-centric relational
transition schema induction** (codex's name; "scale-free" was an overclaim — it's translation/
size *equivariance*, not scale-freedom). Mine jotter's operations for `(action, local object
role, boundary predicate) → delta` schemas, matched on relations (adjacency/containment/
alignment/nearest-in-direction), with support/counterexample/confidence.
- **Cleavage DEBUNKED**: local/equivariant ≠ deducible, non-local ≠ must-witness (a local
  button can reset the board; "mirror the board" is global yet deducible). The real free/paid
  criterion is **model coverage / uncertainty**, NOT spatial locality — locality is only a
  *risk prior*. Same error shape as the graded `m*=∞` debunk: stop tying an epistemic boundary
  to a structural property. The free/paid line is model-coverage, full stop.
- **Pólya** is mostly decoration unless compiled into control policy (the LLM already does the
  verbal moves). Three worth making first-class: analogy/related-problem retrieval by relational
  fingerprint, specialization→generalization (test then anti-unify, counterexamples specialize),
  working-backward regression. Rest stays with the LLM.
- Prior art to lift: OO-MDP / relational RL (closest), ILP / version-space anti-unification, SME
  retrieval, CBR first; avoid full ILP / broad DSL / DreamCoder / EURISKO now.
- Minimum: object-relation graph per state + stored transitions (frame + terminal) + simple
  schema mining + uncertainty-gated piper escalation. Trigger to mechanize: LLM repeats
  trace-inspection across games / a transition recurs 3–5× with role variation / bad guesses
  waste piper / need confidence accounting the LLM can't hold. Until then in-head is fine.

## 2026-06-25 — tn36 generality probe: skeleton general; LS20 leaked into docs AND code

Drove tn36 cold (a click-only configure/visual-programming puzzle: no avatar, no movement, no
path — score 0/7, mapped the surface in 11 clicks) as a generality test of the navigation-built
skeleton. Verdict:
- **The general loop survived** (perceive→hypothesize→act→reconcile→note worked on a radically
  different game). The skeleton is game-agnostic; the strain was entirely in the LS20 vocabulary
  wrapped around it.
- **LS20 leaked into the DOCS** — 6 tells the cold driver flagged: move verbs, "delta localizes
  your avatar", "energy bar", "no change = wall", route/path framing, simmer modeling the wrong
  mechanic.
- **LS20 leaked into the CODE** — jotter's canonical-hash masked a hardcoded bottommost colour-11
  component (pure LS20). tn36's counter is colour-9 on TOP → unmasked → the bar-defeats-dedup bug
  returned: 6 of 12 states were hidden revisits, one config reached 5x. The driver's own "0
  revisits, never re-reached a state" was reading a metric that was wrong on this game.

Fixes (both licensed by witnessed breakage):
- **De-LS20-ified EXPLAINER.md + AGENT.md**: delta→effect-of-action (not avatar); no-change→inert
  region (not wall); energy-bar→generic step-meter (thin depleting strip, any colour/edge); added
  an interaction-discovery start (probe each region control-vs-inert before guessing the goal) and
  a win-model branch point (path / config-match / selection / sequence); simmer's mechanic marked
  an explicit per-game assumption; available-actions set the game type, don't assume navigation.
- **Generalized jotter's counter detection** (graph.py): replaced the hardcoded colour-11-bottom
  mask with `detect_counter(states)` — the move-counter is the thin band touched by ~every
  transition (it ticks unconditionally each action; game mechanics fire only when acted on); mask
  the bbox of its ever-diffed cells. Game-agnostic (keys on behaviour, not colour/position),
  detected from the corpus on load. Verified: run5/tn36 0→3 revisits + 0→3 transpositions (12→6
  unique); run4/run2 LS20 unchanged (18 revisits/2 transpositions, 16 unique); 40 tests pass.
  The move-counter is now a generic factored element (witnessed across 3 games) — the first
  concrete piece of the factored-observer model June proposed.

## 2026-06-26 — tn36 deep dive: it's a timed visual-programming game; the observation wall

Tried to crack tn36 (driven by June, who supplied a screenshot). What it actually is: a
**visual-programming / timed-movement puzzle** — a cursor traces a path through the
checkerboard per a 5-icon "program" (the legend, each icon a cap+stem toggle), the two yellow
`∩`/`∪` glyphs are the target shape, and a big blue **ball** at the bottom is the RUN button.
Per June, the level-1 solution is "all configs on, click the ball → advance." Score is /7
(7 levels).

We did NOT crack it, and the reason is the valuable part — it broke the **observation**
assumption the way earlier games broke navigation/config:
- **The ARC-AGI-3 API has no poll endpoint.** Confirmed against the OpenAPI spec
  (`docs.arcprize.org/arc3v1.yaml`): only `RESET` + `ACTION1–7` POSTs return frames; no GET
  current-frame, no websocket. So observation is strictly *state-on-response* — you cannot
  watch a real-time/timed animation without spending actions, and actions can be valid mid-
  animation. This is an open, acknowledged gap: arcprize/ARC-AGI-3-Agents **#54** (zero-cost
  state updates). piper inherits it: `look` only re-renders the last action's frame.
- **tn36's ball is inert to `ACTION6`.** With all 5 icons verified on, a full sweep of the
  ball region (rows 51–59, cols 32–40) is a counter-only no-op on *every* cell — identical to
  clicking background — while the legend icons DO respond. Ruled out a coordinate error on our
  side. Filed **arcprize/ARC-AGI-3-Agents #89** with a raw-API repro (observed-vs-expected +
  clarifying question, not over-claimed).
- Operational scars worth keeping: ~60% of rapid `ACTION6` POSTs fail silently (flaky API) →
  use retry-until-`actions_spent`-increments; there's a ~1-row click-y offset vs the rendered
  cell; `look` is cached (never refetches live state).

Meta-yield (the point): the generality push found three assumption layers that don't survive a
structurally new game — **navigation** (tn36 is click/program, not move), **config-vs-program**
(the legend is a program, not a config to match), and now **observation** (turn-based,
no live poll). The skeleton (perceive→hypothesize→act→reconcile→note) held throughout; the
instance machinery and the observation model did not. tn36 banked as: blocked behind #54 +
the apparently API-inert run button (#89); not programmatically winnable as-is.

## 2026-06-26 — LS20 drive (1/7) → the framing fix: learn the game, don't finish it

Ran an LS20 "clear levels" drive (run11). Result 1/7, level 1 cleared but ~50 actions wasted.
The failure mode taught the lesson:
- **Findings.** (a) **Deposit rule corrected** (supersedes the "approach-rotation operator"
  build-next from the resource/grade era): the carried HUD pattern must EXACTLY equal the lock
  pattern, then slide the avatar in — the lock's 9s become passable only on an exact match; each
  token pass rotates the carried pattern 90° CW (a 4-cycle), so collect until it matches. No
  approach-direction rotation. (b) **simmer desyncs from piper on an energy reset:** the bar
  empties (~42 moves) → avatar teleports to level-start + loses a life, but the slide model kept
  predicting from the phantom pre-reset position, so BFS routes and 4 deposit-tests all ran
  against an avatar that wasn't there. Guard: re-sync from the live grid after an anomalous delta
  (>100 cells) or every ~35 moves; the reset is invisible to the slide model.

**The framing correction (June, two passes):** "take action only as a means to expand the
hypothesis graph"; "the goal isn't to finish the game, it's to learn how it works." My drive
prompt had it backwards — goal=score, actions as ends — so the driver just moved (50 moves, 0
notes, no reasoning on any action; `arcg notes` empty) and never noticed the desync because it
never reconciled prediction vs reality. Lack of graph-discipline IS what cost the run.
- **EXPLAINER.md reframed:** the goal is to learn how the game works; score is a byproduct that
  confirms the model. Every action is a means to expand the hypothesis graph, never an end; if
  you already know the outcome (witnessed hypothesis entails it, or simmer predicts it), don't
  act. Added principle "Action serves the graph"; loop is now predict→act-to-test→reconcile→note.
- **PLAN.md jotter invariant tightened (June):** "all actions in jotter must point to an action
  node and a hypothesis node." Action-provenance is now a MANDATORY DUAL ref — `dagger:<id>`
  (the action node executed) AND `arbor:#<id>` (the hypothesis tested) — on every action, no
  exceptions (even a probe names an open hypothesis + a probe node). This is epmem linking
  pmem↔smem, and the structural enforcement of "action serves the graph": an action naming
  neither executes no plan and tests nothing, so it is rejected. Dedup key becomes
  `(state, action, dagger-node, arbor-node)`; the old "prose at the pre-hypothesis frontier"
  exception is dissolved.

## 2026-06-26 — the framing fix VALIDATED (run12) + a concrete gap

Re-ran LS20 under the corrected framing (learn-the-game / action-serves-the-graph / note the
hypothesis+plan-step per action, reconcile after). Controlled before/after vs run11 (same game,
old framing):
- **run11** (goal=score): 50 moves, **0 notes**, no reconciliation, chased a phantom
  simmer/piper desync, 1/7.
- **run12** (goal=learn): **15 moves, 9 substantive notes**, every action bracketed by
  predict→reconcile, **killed+corrected 2 hypotheses** (H2 collect-scores, H3 proximity-scores),
  **caught the simmer-blind win surprise**, 1/7 as a byproduct. It isolated causality (L1 moves
  9-14 carried a matching key without scoring; only lock-entry scored) and abstained from
  re-noting predictable traversal and from grinding L2 (confirmatory → don't act).
- **Win model cracked** (corrects the earlier "approach-rotation" guess): LS20 = 7-level
  key-matching locksmith. Toggle-tokens (0/1) edit a carried KEY (bottom-left HUD 3x3, persists
  across levels); a maze box shows the LOCK target; when key==target, driving the avatar INTO
  the lock OPENS it (colour-9 lock stops blocking) → +1 + maze regen. The lock-open is the
  simmer-blind surprise (`step()` correctly predicts blocked; it's the [14] 1465-cell ✗).
  Documented in engine.py docstring (commit 06920f9, benign, 40 tests pass).

**Concrete gap surfaced:** `arcg notes` is SESSION-BOUND — the graph (now the deliverable)
**vanished on `arcg end`**; only trace.jsonl preserved the note text. Fix needed: persist the
hypothesis graph durably (jotter), not in the session. **Open contradiction:** run11 said the
token rotates the key 90°CW; run12 says it flips a bit — the key-edit mechanic isn't pinned.

Takeaway: June's framing correction (goal = learn, not finish; action serves the graph; dual
provenance) didn't just make the trace auditable — it made the driver materially better at the
task (cracked the win model in 15 actions vs a 50-move flounder). Graph-as-goal / win-as-
byproduct is empirically the right objective.

## 2026-06-26 — run13: Q1 contradiction settled (ROTATE); simmer energy-rate gap

Graph-disciplined LS20 drive seeded with run12's validated win model, tasked to resolve the
open questions. 14 notes, 38/80 budget, 1/7 (byproduct), no engine edits.
- **Q1 RESOLVED — the toggle-token ROTATES the carried key 90° CW** (whole 3×3), witnessed
  twice with a discriminating test: predicted rotate vs toggle vs set, reconciled — toggle
  killed (two cells change, not one), set killed (lvl2 result ≠ lvl1's, so not a fixed value).
  **Settles the run11-vs-run12 contradiction: run11 (rotate) was right; run12 ("flip a bit")
  was wrong.**
- **New mechanics** (each predict→reconcile): token REGENERATES on avatar-leave (oscillate for
  multiple rotations); a within-level DEATH-reset reverts the carried key to its level-entry
  value (survives wins, not deaths); colour-8 = lives; pickups (11) refill the bar to full.
- **Q2 (direction-agnostic trigger) NOT witnessed — budget-blocked.** Lvl2's lock affords a
  DOWN entry (geometry characterized); the win-model predicts it opens regardless of direction,
  unconfirmed.
- **Concrete gap: simmer under-models energy.** The bar depletes ~2 cols/move; `_deplete_bar`
  removes 1 → the agent under-budgeted, ran the bar to 0 mid-route, ate a reset (wiped its
  rotations, cost Q2). Routing (avatar position) unaffected, but energy-budgeting is — and
  energy now gates route feasibility. `simmer test` 10/38 (the bar mismatch misses ~every move).
- Notes-persistence gap (run12) still stands: recovered the graph from trace again; `arcg notes`
  died with the session.

The framing keeps delivering: resolved a standing contradiction with a real test, banked four
mechanics, caught the run11-killer (energy reset) as a surprise instead of grinding through it,
stopped economically. Remaining friction is tooling (energy fidelity, note persistence), not the
driver's reasoning.

## 2026-06-26 — intent: move discipline from prompt-suggestion to harness-enforced gate

Realism check (June): **prompts are suggestions.** The EXPLAINER/AGENT framing is guidance to
an LLM driver, not a guarantee — it can be ignored (run11 ignored "note what you learn": 50
moves, 0 notes). So prompt-level discipline isn't robust; it rides on the driver's goodwill.
Robustness comes from the **harness ENFORCING** the invariants — the project's own division
("modules = harness: hold + gate, mechanical; driver = reasoner: attend + decide") and the
poka-yoke boundary ("guard invariants, pre-API; a free bounce, not a backstep").

INTENT — migrate the disciplines we've been writing as prompt text into harness-enforced GATES,
so they hold regardless of driver (LLM or coded policy). All of these guard **process
invariants** (properties of the reasoning loop), NOT game hypotheses — so they respect "guard
invariants, never hypotheses": the harness enforces *how you reason*, never *what the game's
rules are*.
- **Dual-provenance gate** (PLAN.md: every action → an action-node + a hypothesis-node): make it
  an actual GATE — the act/commit path REJECTS an action lacking both refs, with a typed
  instructive error. A blind action becomes structurally impossible. (Today: the prompt merely
  asks the driver to `note` both.)
- **Hypothesis-before-act gate**: the act path requires a recorded hypothesis + prediction
  first; a bare move that names no open question is refused pre-API.
- **Reconcile automatically**: the harness computes prediction-vs-reality (the surprise) on
  every act — the kill/witness is mechanical, not an optional habit.
- **Facts → jotter, automatically**: the planner/harness auto-consults `jotter effects` for
  resource/quantity facts rather than relying on the driver to remember to ask — a fact-check
  the harness performs, not a discipline the prompt requests.

This is the ratchet applied to the DISCIPLINE itself: the prompt is the in-head version; run11
showed it visibly breaks (ignored), and run12/run13 showed it works *when followed* but only on
goodwill — so codify the gate. Each gate is poka-yoke (fires pre-API, zero budget, names the
rule in the error so any driver learns it by hitting it). The prompt stays as onboarding; the
GATE is what makes it robust. Not built yet — recorded as the direction; the trigger has fired.

## 2026-06-26 — hypothesis generation: generous diverse branching is the creative act

June: hypothesis generation should be GENEROUS with branching for DIVERSITY — that's the
creative act. Design principle for arbor's `abduce` and dagger's win-down:
- **Be lavish at generation because it's FREE.** Branching = abduction = the uberty pole, which
  runs in-head/simmer at zero budget; the bench gives infinite thinking. The whole economy is on
  the VERIFICATION side (paid actions/tests). Stinginess at generation is a category error.
- **Diversity, not volume — and it's information-optimal.** Diverse hypotheses make DIFFERENT
  predictions, so each paid test discriminates many at once; clustered variations predict the
  same delta and waste tests. A diverse hypothesis set IS the optimal experiment design
  (maximizes information per test — the e-value/discrimination view). The creative act at
  generation is what makes the ruthless step at verification cheap.
- **The asymmetry is the engine:** generous + diverse at generation (uberty, free); ruthless +
  convergent at verification (security, paid — one counterexample kills, the differential test,
  the oracle). Diversify, then filter. The wide diverse frontier also dodges the local-optimum
  trap perturbation hill-climbing falls into — diversity IS the global search.
- **Lands in:** `abduce` returns a DIVERSE FRONTIER, not a single claim; win-down branches into
  diverse candidate decompositions. Pairs with from-kill: from-kill gives DEPTH (the
  counterexample-covering successor), generous branching gives BREADTH around it.

## 2026-06-26 — dagger induction mechanism: HTN-Maker + DreamCoder, read in full

Fetched CURRICULAMA/HTN-Maker (arXiv 2404.06325) and DreamCoder (2006.08381) for the
decomposition-INDUCTION mechanism dagger had sketched least. They map one-to-each onto the two
roots and fix each other's failure:
- **Win-down = goal regression (HTN-Maker).** Regress the goal backward through a SCORING
  trace's action suffix → the regressed precondition is the method's domain, the goal its
  codomain. This is the concrete mechanism to COMPUTE a dagger node's pre/post (the
  commuting-factorization typing) from a real winning trace — we had the typing, not the
  mining.
- **Act-up = compression (DreamCoder).** Promote action-subsequences that repeat ACROSS traces
  to reusable sub-DAGs. (Skip DreamCoder's version-space λ-refactoring — our "programs" are flat
  action sequences; finding repeats is cheap. Take the idea, not the machinery.)
- **THE KEY TRANSFER — MDL keep-criterion fixes the bloat.** CURRICULAMA's one unsolved failure:
  learned-method count grows WITHOUT BOUND (utility problem; they keep every candidate).
  DreamCoder's cure: keep an abstraction iff it REDUCES total description length
  (`−logP[L] + Σ prog-len`). So: mine by regression, KEEP by MDL-compression. This is the
  "compress" half of compress-and-unfold made quantitative ("keep iff it shortens the corpus's
  encoding"), and it's the anti-bloat guard HTN-Maker lacks.
- **Annotated-task burden dissolves via landmarks — ours are free.** CURRICULAMA mines landmarks
  (facts that must hold en route) → subgoals → easy-to-hard curriculum (expand the plan window
  backward). dagger's landmarks come free from the score sub-conditions (X/N = N subgoals) + the
  witnessed intermediate states jotter already records along a winning trace ("key==target"
  before "lock opens"). Subgoals mined from jotter, not annotated.
- **Dream with simmer.** DreamCoder trains its search-guide on FANTASIES (library samples solved
  in imagination) because real tasks are few. simmer is our fantasy engine: roll out
  hypothetical decompositions FREE to validate/stress the cache without spending a real action.
- **Already have (confirmed):** commuting-factorization check = their execution-validation;
  from-kill = collapse-on-rot; JIT-on-miss = wake-phase search. The papers confirm our
  validation is the right kind, don't ask us to add one.
- **Don't copy:** HTN-Maker hand-annotation (use landmarks); "keep all mined methods" (use MDL);
  DreamCoder's version-space machinery + year-of-CPU (overkill for flat action seqs).

Net: dagger = goal-regression (win-down) + repeat-compression (act-up), candidates mined from
scoring traces in jotter, KEPT by an MDL criterion, validated by the commuting check, dreamed in
simmer. The MDL keep-criterion is the load-bearing import — it's what makes the decomposition
cache converge instead of bloat.

## 2026-06-27 — layers of determinism: condition / enforcer / strength

Named the harness-gate direction (the 2026-06-26 "prompts are suggestions" intent) into a bounded
vocabulary, prior art = `documents/sweep` (andon, poka-yoke intake contracts, `andon_unexpected`
metric). Separated two objects DbC had been conflating:
- **condition** = pre/postcondition (the spec); **enforcer** = pregate/postgate (the mechanism
  that makes it hold or refuses). A pregate enforces a precondition, a postgate a postcondition.
  This unifies the process disciplines with dagger's existing composition conditions (same Hoare
  object).
- **strength** = ratchet **prompt → gate → matcher** (one condition pressed three ways: stated /
  exact-enforced / tolerantly-enforced). matcher is the gate's decision procedure for inexact
  conditions (= the planned prose→subsumption hardening), not a separate layer.
- Names bounded by construction: `{module}-gate` per pre-API precondition — **dagger-gate** (live
  plan node), **arbor-gate** (live hypothesis + prediction), **jotter-gate** (plan vetted vs
  `jotter effects`); **postgate** = reconcile (`jotter diff` → witness/kill, surprise engine made
  mechanical; fires only when a simmer plan exists). Dual-provenance needs no name: dagger-gate ∧
  arbor-gate gives it free.
- **Three exits, crash is default.** hold / bounce (known violation, instructive, zero budget) /
  crash (unanticipated, halt loudly, no silent swallow). Second ratchet **crash → handle**: promote
  a recurring crash to a bounce or recovery case-by-case; crash count falling = `andon_unexpected`
  dropping. Boundary holds: crash on process failure, never on a wrong hypothesis (that's a postgate
  kill).
- sweep's lesson carried over: shipping the check ≠ migrating callers (`pokayoke.py` shipped 6
  intake fns, 0 callers). Each gate is two units: define the check, then route the act/commit path
  through it. Only the second moves the metric.

Written to PLAN.md (under design-by-contract, §poka-yoke). Not built yet — this is the spec.

## 2026-06-27 — gates built end-to-end; dag-building is a matcher, not structure

Built the gate scheme (commit 101d605). New `arcg/gates.py` = `UsageError` + four gates, each
with the three exits (hold / bounce=typed UsageError / crash=uncaught). Single commit boundary
= `layer0_protocol.act()` (the API commit `c.act()` + the jotter commit `append_transition` both
live there; every caller funnels through it). Routed:
- **dagger-gate** / **arbor-gate** (pre): fire at the TOP of `act()`, before `store.load()` —
  pre-API, zero budget, zero I/O. Well-formedness only (`dagger:<id>` / `arbor:#<id>`); arbor
  and dagger have no module/registry yet, so liveness is a TODO.
- **postgate** (post): after the frame lands, only when a `pred` exists — `piper ⊕ simmer` →
  witness/kill.
- **jotter-gate**: defined+tested but routing DEFERRED. Its home is the planning seam
  (`dagger.plan`, unbuilt); per-act vetting would bounce every novel action and block
  exploration. Flagged, not fake-routed (avoids another pokayoke "6 checks, 0 callers").
Migrated all callers (cli `act` + `--dagger`/`--arbor`, intent move/click/interact/undo, replay)
through the pregates. Full suite green (52).

Design refinement (the one to keep): **building the action dag is not a structural lookup.** An
edge B→A is valid when `B's postcond ⊨ A's precond`, and that `⊨` is subsumption — a
**generalize-or-specialize judgment per edge** (does the concrete effect specialize the general
goal, or does the goal generalize up to meet it). So dag-building runs a **matcher** (tolerant —
a wrong call is a wasted free rollout, not a broken plan), not a **gate** (exact). Consequence
for the gate I built: the dagger-gate's "live node" check is a thin reader of the dag's
reachability verdict, never a registry `==`; the judgment lives upstream at `dagger.plan`. This
reframes task #6 (dagger-matcher) — it's the **engine of dag-building**, not a stretch bolt-on.
TODO sharpened in `gates.py::dagger_gate`.

Also fixed the autoenv annoyance: the project `.env` (just `ARC_API_KEY`) was being read as an
autoenv script and prompting `Authorize this file? (y/n/d)` on every shell, eating heredoc stdin.
Moved the key to `~/.zshrc`, removed `.env` (autoenv has nothing to trigger on; `os.getenv` still
resolves it in the interactive shell).

## 2026-06-27 — evidence layer: content-addressed trace + live low-budget run

Long design thread (verifiable-knowledge → hypothesis↔(proto-)node → verdict provenance via git
commit/range/branch/annotated-tag → series=compound-node=commit-range), then a codex blindspot
pass. Codex's load-bearing hits, kept as standing corrections (not built yet):
- **idempotent storage ≠ idempotent knowledge.** Our guarantee is correctly scoped to the EVIDENCE
  log (append-only, monotone, content-addressed). BELIEF (verdicts, credence) is a derived,
  non-monotone, versioned query that sits ABOVE it. Don't conflate.
- a re-runnable verdict only reproduces if the whole evaluator stack is frozen → a surprise warrant
  is a CLOSURE (source-repo commit + arbor snapshot + input), not "two hashes".
- verdict-id = hash(canonical record), NOT a git tag sha (tag hashes fold in tagger/timestamp).
- kill the JUSTIFICATION, not the claim (ATMS granularity); first divergence is a CANDIDATE, not
  the culprit; the tolerant matcher must not authorize a PAID action (certified vs possible
  composition — routes into the dagger-gate); simmer evidence is correlated, only piper witnesses
  are independent supports.
- HELD against codex's prod-scale push: no event store / CAS / Nix / full ATMS. Single-agent
  serial, correctness over wall-clock, git+jsonl is the right cheap substrate (user call).

Built the unambiguous floor of the evidence layer: `jotter.graph.trace(rows)` — a content-addressed
trace object `{id, initial, steps, final}`, the series-evidence unit, hashed directly (not a git
range, whose meaning shifts under rewrite/merge). States under the same counter-masked identity as
the dedup graph. `jotter trace` CLI + sanity test. Full suite 60.

Live low-budget run (LS20, budget cap 6, 5 moves):
- trace `0ed590a18109`, reproducible across re-reads (content-address holds).
- dedup caught down-blocked-at-wall: `ACTION2` self-loops on the same masked hash while `effects`
  shows colour-11 (the counter) still ticking −2 — position no-op, budget meter still spends. The
  two evidence views disagree correctly.
- `jotter audit`: gapless stamps 1..5, piper actions_spent 5 == jotter 5 (faithful, no drops).
- gates held live: every `arcg move` routed through dagger-gate + arbor-gate and passed.
Score 0 (5 unguided moves). The gate contract layer survived a real API run.

## 2026-06-27 — dagger backed by a SQLite jotter submodule (db is truth, render for inspection)

Design call (resolving "where does the dagger data structure live?"): it's a prose md file until
it outgrows context, then a lightweight db — PLAN.md's own ratchet. But the render insight flipped
it: a `render()` projects the db OUT to prose for inspection, so you get in-context legibility AND
never write a brittle prose parser (truth flows db→prose, one direction). That kills the md-file
stage's only advantage, so we skipped straight to the db. Held against codex's prod-scale push:
SQLite (stdlib, single file), NOT an event store — single-agent serial, correctness over wall-clock.

Two decisions locked:
- **node identity = authored ANCHOR** (write-once, like arbor's #4), not a hash of the prose.
  Dodges codex's near-synonym proliferation; the matcher stays on the predicate, the anchor is
  identity.
- **belief stays deferred.** The schema is evidence/skeleton only (nodes); verdicts/credence wait
  for the first verdict, when PK-idempotent set-add and belief-as-query both start paying.

Built:
- `jotter/db.py`: nodes table keyed by anchor (PK). `put` = `INSERT ... ON CONFLICT DO UPDATE
  WHERE rank(new) > rank(old)`, so status domination (killed > live > open) + idempotency are
  STRUCTURAL (PK-enforced), not policed. `render(conn)` -> markdown. db.py is dagger-agnostic
  (knows the table, not the matcher), staying below dagger in the import order.
- `dagger/dag.py`: verbs (init/get/plan/decompose/put/merge/live/render) re-pointed at the store;
  Node identified by anchor; `connect()` -> STATE_DIR/graph.db, ':memory:' for tests.
- tests rewritten for the sqlite model; DAGGER.md §interface doc-synced (anchor identity, db→prose).
Full suite 60. Verified: render lists leaves + a killed compound + apex; get/live resolves the
killed node to live=False — the reader the dagger-gate liveness TODO was waiting on. Commit 475f65e.

Open forks: (1) wire dagger-gate to call dagger.live (reader now exists; needs a conn on the act
path). (2) the first verdict, which lights up the belief tables. Codex's standing corrections still
parked: closure-warrant for surprises, kill-the-justification (ATMS granularity), first-divergence
is a candidate not the culprit, matcher must not authorize a paid action.

## 2026-06-27 — the serial loop (driver): gated, simmer-reconciled, frontier-exploring

Built the synchronous loop (PLAN.md §the-serial-loop) as `driver/` — importable `run`/`decide` with
a thin `drive` CLI over the same surface (the tools are both CLI and Python, per the convention).
The loop: perceive → simmer.step predicts free → act through the GATED path (l0.act → dagger/arbor
pregates → jotter record → postgate reconcile piper⊕simmer) → decide. Seeds the dagger graph
(init with the game's available_actions) so the dagger refs resolve to real leaves. Cognitive steps
(arbor abduce/witness, dagger.decompose) deferred — the loop explores, it doesn't yet form beliefs.

Live drives on LS20 drove the policy fixes (the value of a real run):
- **simmer is accurate on LS20 movement.** 0 surprises, and I ground-truthed it: simmer.step matches
  the recorded reality 20/20. The hand-written slide+deplete model captures LS20's moves+counter, so
  the 0 is real, not a postgate bug. (It hasn't been tested on the lock mechanic — exploration never
  reached it.)
- **decide bug 1 — counter confound.** Every action depletes the move-counter (a grid change), so
  "prefer a simmer-predicted move" thought every action moved. Fixed: detect movement on the
  COUNTER-MASKED state (jotter's hash), not the raw grid.
- **decide bug 2 — oscillation.** Greedy-local novelty round-robins (up then down undoes itself),
  exhausting the neighborhood then cycling (3 unique states / 20 actions). Fixed: frontier-seeking —
  try UNTRIED actions from the current state first, and when it's fully expanded, BFS the known
  masked-state graph to the nearest state that still has an untried action and head that way. Result
  3→9 unique states, 4→23 edges in 25 actions.
- simmer now declares coverage (`MODELED`); `_predict` returns None for unmodeled actions so decide
  PROBES them rather than skipping them as walls (PLAN's "spend where simmer lacks coverage"). Moot
  on LS20 (only ACTION1-4 offered) but correct for games with interact/click.

Score still 0 — exploration isn't goal-directed (no dagger.plan decomposition, no key/lock model).
That's the next layer: a plan toward the lock + the win-trigger, which is the cognitive step. Full
suite 62. `drive` registered in [project.scripts].

## 2026-06-27 — the reasoner: tool-using agent, one experiment unit per session

Pivoted off the one-shot mega-prompt. First tried suggesting goal-decomposition (>=2 subgoals) in
the llm_agent SYSTEM prompt and observed traces: the agent used the `plan` field but mostly held ONE
active subgoal, and it was bottlenecked upstream — stuck in exploration because raw perception is
confounded by the move-counter (the SAME confound that looped the driver), so it never reached the
planning regime. Conclusion: don't gate branching; the binding constraint was perception.

So the real fix is tool freedom (PLAN.md's "Claude Code = reasoner"). New `agents/reasoner.py`: an
outer harness starts the game + owns its lifecycle, then spawns a FRESH agentic `claude` headless
session per experiment unit (`--allowedTools` = the project CLIs, `--max-turns` backstop). The
session re-hydrates from the persistent memory, does ONE unit (test one hypothesis with the fewest
real actions, record it), then STOPS — bounded context, refreshed each unit; the caches carry across.
This is the "memory is a cache" loop the persistent stores + render were built for.

Live unit on LS20 (11 turns, $0.42, ONE action of 8 spent) validated the whole pivot. The agent
used `arcg objects` (connected components) to isolate the moving piece and `jotter effects` to name
the counter, and correctly found: "move right slides a 5-wide c+9 cursor block (not the avatar);
colour-11 is a position tracker; the avatar is stationary" — seeing straight through the confound
that flailed the one-shot agent ("ACTION3 x4 didn't move"). It even teed up the next unit's
hypothesis then stopped. Tool freedom dissolved the perception bottleneck.

Gap the run exposed + fixed: the agent recorded via `arcg note`, which is SESSION-scoped, so
`l0.end()` wiped it. Durable memory must outlive the session — moved findings to `.arc/findings.md`
(jotter's corpus was already durable; the action survived). Context-refresh now works across runs.

Also built the `dagger` CLI (render/get/plan/decompose/init) so the reasoner can inspect and grow
the plan graph. `reason` + `dagger` registered in [project.scripts]. Full suite 62.

## 2026-06-27 — attribution gate: the sleep pass must ground its own verdicts

Audited a consolidated graph and caught the failure mode the whole design is supposed to prevent:
`vert-blocked-adj-c9`, a confident `killed` nogood whose post claimed vertical movement is blocked
"when colour-9 is adjacent below". The trace had the exact minimal pair to test it — A1 moves up at
one cursor column (`b765`), A1 is a no-op at another (`5695`) — and `jotter show` on that pair shows
the discriminating feature is **colour-4** (a wall overhang), with colour-9 *constant* across both
(it's the cursor's own body). The sleep pass named the one variable the contrast rules out. The kill
was right (the block is real); the *attributed cause* was hallucinated. Nothing in the store could
have caught it: `Node` had no provenance slot and `decompose` never checked the post against jotter.

Fix: make attribution the consolidate agent's job, not a downstream auditor's, and key it on status
so the pass stays free to dream.
- `Node.evidence: tuple[str,...]` + an `evidence` column (in-place `ALTER TABLE` migration; legacy
  rows back-fill to `[]` = speculative). `render`/`get` mark every compound `grounded` or
  `speculative`.
- The gate (`decompose`): `open` is a hypothesis — evidence optional, renders `speculative`, dream
  freely. `live`/`killed` is a VERDICT — must cite the episode(s) that established it, and a CAUSAL
  post (a `when`/`because`/`drag`/`adjacent` tripwire) must cite a CONTRAST PAIR (≥2 refs); one
  episode can't isolate a cause. The semantic check (does the named cause actually DIFFER across the
  pair?) is the agent's `jotter show` self-check, now spelled out in `CONSOLIDATE_TASK`.

Live drive #1 (run15) validated it cleanly: on a thin trace with no blocked episode, the agent wrote
`null-cycle [killed, grounded]` citing its round-trip pair `0,1` (verified: returns to the exact
start hash), and — crucially — demoted the same colour-9 claim to `[open, speculative]`, narrating
"needs contrast pair to re-establish". The hallucinated verdict became an honest dream because the
evidence wasn't in the corpus. Discipline tracks evidence, not the model's confidence.

Drive #2 (run16, longer) exposed two real bugs:
- **The apex was killable.** The agent ran `decompose win-game ... --status killed` and the gate
  passed it ("win game" is non-causal, evidence supplied), killing the root goal →
  `plan("win game")` becomes a permanent HOLE; winning is unplannable. Fix: `decompose` refuses the
  `win-game` anchor (a win recipe is authored under its own anchor with post "win game", matched by
  `entails`); `dag.put` refuses to ratchet the apex off `open` as defense-in-depth.
- **Status-ratchet silently dropped grounding.** `db.put`'s `ON CONFLICT` updated status only, so a
  node seeded empty/open and re-put as a verdict kept the *empty* children+evidence — manufacturing
  a gate-forbidden `killed`-with-no-evidence row at the storage layer, and breaking the
  dream→verdict lifecycle (promote an `open` node with its pair → the evidence vanished). Fix: a
  ratchet now carries `evidence` and fills empty structure once; non-empty structure stays
  write-once. `open/speculative/()` → promote → `killed/grounded/(b765,5695)` now sticks.

Operational: consolidate timeout 420→660s (the self-check adds `jotter show` turns; run16 timed
out), and the wake prompt now nudges toward probing edges/obstacles so a *blocked* step actually
gets recorded — without it the deterministic LS20 prefix just re-derives the same 3-step trace.
Full suite 71.

## 2026-06-28 — watch the loop learn: a remediation bug, and prompts → progressive disclosure

Ran the wake/sleep loop on LS20 (`reason --units 3 --cycles 1`, checkpointed off the existing
graph, live session in a throwaway dir so `.arc` stays clean) and *watched it learn into the
tools* — wake recorded findings to jotter+notes, sleep consolidated into dagger. Three things the
watch surfaced (the probe-of-the-system payoff a score line would have hidden):

- **B — remediation was silently broken.** The sleep pass logged "pruning skipped (notes
  unreadable)". Root cause: `CONSOLIDATE_TASK` tells the pass to re-hydrate with `arcg notes`, but
  `_BACKWARD_ALLOWED` granted only `arcg note`/`arcg forget` — `notes` is a distinct subcommand
  (`cli.py` registers note/notes/forget separately), so the read was denied and the pass could
  never see the notes to prune them. The corpus grows unbounded — "memory is a cache" defeated.
  Failing-test-first (`test_consolidate_pass_may_read_the_commands_it_is_told_to`: every `uv run
  arcg <cmd>` the task names must be permitted by the allowlist), then granted `arcg notes:*`.
  **Live-validated**: a fresh sleep pass then read the notes, **pruned 4**, and consolidated
  `move-wall-block [live, grounded, ev 2,8]` — the *correct* generalization of the left-blocked
  constraint (real cause = colour-4 wall collision, isolated by a step-2-open vs step-8-walled
  pair), even reconciling the old `vert-blocked-adj-c9` hallucination (mis-attributed to colour-9
  adjacency; real cause is the wall).
- **A — a forced verdict.** The same run had promoted `lateral-drag-c9` to `[live, grounded]` by
  reading the cursor's own colour-9 *tail* sliding as "dragging colour-9 objects" — conflating the
  cursor's body with external objects, though the cycle's own wake notes said the opposite ("tail
  is the cursor's shadow"; "the cage colour-9 did NOT drag"). The cited pair shows cursor+tail
  moving, not external-object drag. Same class as the run16 hallucination, one level up: the gate
  enforces *≥2 refs* but can't enforce that the pair *isolates* the claim. The fix is not another
  rule — it's the sleep goal stated plainly (below): consolidate what's CLEANLY grounded, **leave
  the ambiguous ones for the next pass**. A forced verdict is worse than a deferred one.

**Prompts → progressive disclosure (the larger change).** The two task prompts had grown into
~50-line manuals duplicating — and outliving the accuracy of — what `--help` should own (e.g.
`dagger decompose --help` already carried the attribution rule the prompt re-explained). Rebuilt
per the PLAN.md onboarding design: the prompt is the **map** (layer 1, role-scoped — wake vs sleep
*is* the first disclosure split), `<tool> --help` the reference (layer 2), `<tool> <cmd> --help`
the specifics (layer 3).
- `FORWARD_TASK`/`CONSOLIDATE_TASK` are now short, goal-based maps that defer to `--help`. The
  sleep map leads with its goal verbatim: *consolidate epmem (jotter) into pmem (dagger); promote
  the clean, leave the ambiguous for the next pass.*
- Reference migrated into `--help`, kept healthy: `dagger` no-args prints a driving-contract;
  `dagger decompose --help` carries the full discipline (status meanings, the contrast-pair
  `jotter show` self-check, and the leave-ambiguous rule = the principled fix for A); every `arcg
  <cmd> --help` now surfaces its description (added `description=help` in the `add` helper), and
  `arcg look --help` carries the EXPENSIVE cost-note moved out of the prompt.
- **No hard turn cap.** The session is bounded by its GOAL (the prompt's STOP), not a turn count;
  `--max-turns` is dropped (was 14/30 — the 14-cap once starved the sleep pass before remediation),
  `timeout` is the runaway backstop only. `_build_cmd` extracted so this is unit-tested.

New tests pin all of it (light/goal-based maps; wake+sleep allowlists grant what their maps name;
no `--max-turns` by default; `dagger decompose --help` carries the discipline). Full suite 76.
