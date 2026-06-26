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

Next direction under discussion (not built): the hypothesis generator as **scale-free,
boundary-conditioned relational pattern inference** over jotter's past operations (object-local
patterns, translation/scale/grid-size invariant → game-agnostic; mechanic patterns are local &
scale-free = deducible, non-local effects = goal/terminal = must-witness). June frames the
heuristic vocabulary via **Pólya** (working-backwards = win-down, "related problem"/analogy =
the scale-free retrieval, decomposition = dagger, look-back = write-back, specialization =
simmer-test, generalization = the scale-free rule). To be reviewed before any build.
