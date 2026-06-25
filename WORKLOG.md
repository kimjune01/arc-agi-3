# Worklog

Append-only log of what we learn (rules, measurements) and decide (architecture,
scope). Newest entries at the bottom. Durable findings also live in NOTES.md;
this is the dated trail of how we got there.

---

## 2026-06-24

### Rulebook verification (against docs.arcprize.org)

Checked our planning assumptions against the official docs/OpenAPI. Sources:
methodology.md, actions.md, game-schema.md, full-play-test.md, arc3v1.yaml.

**Action space — confirmed and enriched.** RESET + ACTION1-7.
- ACTION1=up, ACTION2=down, ACTION3=left, ACTION4=right
- ACTION5=interact/select/rotate
- ACTION6=complex, requires (x,y), each 0-63
- **ACTION7=undo**  ← did not expect this
- Matches our live observation: ACTION3 slid the `12`-block left. So the
  `12`-block being the avatar is consistent with ACTION3=left.

**ACTION7 = Undo changes the backtracking story.** We had assumed "no cheap
rewind — backtracking means RESET + replay N." False. A single-step undo exists
and costs 1 action. So Layer 2 has TWO backtrack mechanisms:
- `undo` (ACTION7): O(1) action, one step back. Preferred for shallow revert.
- reset + replay: O(N) actions, arbitrary jump. Only when undo can't reach.

**Scoring is efficiency (RHAE), not a hard cap.** `level_score =
(human_baseline_actions / ai_actions)^2`, capped at 1.15x human efficiency.
Incomplete games get proportionally reduced max. Exceeding the per-level action
cutoff on every level → 0%. So:
- There is no documented fixed per-game action budget; cost is *continuous*.
- Every state-changing action lowers the score. Internal reasoning/tool calls
  that don't change state do NOT count.
- This CONFIRMS "replay counts against the budget" — but as an efficiency
  penalty, not a cliff. Probes, replays, and backtracks all erode RHAE.
- Human baseline = upper-median (fewest actions) of first-time human players.

**Determinism is NOT documented.** Neither game-schema, methodology, nor
full-play-test states that equal input sequences after RESET reproduce state.
The docs do ship "replayable runs" + a Playback agent, which *implies*
reproducibility — but it is unconfirmed. So:
- Determinism stays a HYPOTHESIS, not a relied-on guarantee.
- This raises the value of Layer 2's determinism check: `restore` replays anyway
  (we pay the actions regardless), so comparing each replayed frame to the cache
  is a free measurement of an unverified property. First real experiment.

**RESET semantics.** Omit `guid` → new session. Provide `guid` → reset; if any
action was taken since the last level transition, only the current level
restarts, else the whole game. Two consecutive RESETs = fully fresh game.
`win_score` (win_levels) = number of levels to complete.

**Open / unverified.**
- The exact per-level action cutoff (the "0% if exceeded" threshold) — not
  found numerically. ("5x" was a guess; confirm before relying on it.)
- Does RESET itself count as an action toward RHAE? Replayed ACTIONs do; RESET
  treatment unclear.
- Whether ACTION7/undo counts toward RHAE (almost certainly yes — it changes
  state) and whether undo is always available.

### Architecture decisions (planning, pre-code)

- **`arcg` is the sole interface to the game and its abstractions.** Nothing
  above it touches the raw API. `ArcClient`/httpx is sealed behind Layer 0.
- **Layered command surface, strict downward-only dependencies:**
  - Layer 0 Protocol — `games/start/act/end`; only importer of `ArcClient`;
    hides card_id/guid/cookies.
  - Layer 1 Perception — `look/diff/status`; renders stored frames, no API.
  - Layer 2 State & determinism — `history/snapshot/restore/peek` + budget meter;
    exploits "state ≡ action sequence".
  - Layer 3 Memory — `note`.
- **Modularity discipline: no layer may import from a layer above it.** Enforced
  by a test that walks the import graph; only Layer 0 may import the client.
- **Pragmatic single surface.** Each subcommand is a function; the CLI and the
  programmatic policy both call the same function (no subprocess tax). Same
  surface in practice.
- **Layer 2 is a scientific instrument, not a search engine.** Branching 7 under
  an efficiency budget makes MCTS/blind search pointless. Snapshot/restore is for
  (a) counterfactual probing to learn mechanics, (b) backtracking from dead ends
  — driven by the agent, not an automated search harness.
- **Determinism handling = deferred hook.** `restore` returns a verdict
  (replayed frame == cached?). What to do on mismatch (record/fail/trust) is a
  policy decision to make after the layering exists.
- **Cache is the budget-saver.** `sequence → frame` lets the agent `peek` any
  visited state for free (no API); spend actions only to reposition the live
  session. With ACTION7 undo now known, shallow backtrack may not even need a
  replay.
- **Minimal v1 scope:** refactor existing client/perception into Layers 0-1, add
  Layer 2 `history/snapshot/restore/peek` with determinism check + budget meter,
  add the import-boundary test. Re-point the programmatic `LLMAgent` at the same
  functions.

### Layer taxonomy refined

- **Layer 0 = raw protocol only.** `games/start/act ACTION1..7/reset/end`. Speaks
  ACTION-numbers + frames. ACTION7/undo is just a raw action here. Sole importer
  of `ArcClient`; hides plumbing (guid/cookies) but not game semantics.
- **Layer 1 = agent action intent + perception.** The semantic surface where the
  agent operates in game terms, never ACTION-numbers.
  - intent verbs: `move {up|down|left|right}`, `interact`, `click x y`, `undo`
    → translate to ACTION1-7.
  - perception verbs: `look`, `diff` → render Layer 0 frames.
- **Caveat (logged):** the intent→action mapping is the documented DEFAULT; the
  API says the real effect "depends on the title." So Layer 1 intent encodes a
  HYPOTHESIS the agent verifies per game via deltas (ACTION3=left held on LS20).
  Keep Layer 0 `act ACTIONn` as the escape hatch when the convention doesn't fit.
- Layer 2 (state/determinism) and Layer 3 (memory) unchanged. `status`/budget
  surface at Layer 2 (depends on the budget meter).

### Stack is open-ended

- The layering is a growing STACK, not a fixed 4. Many more layers will be added
  (plausible upper floors: world-model/learned mechanics → planning → policy →
  meta-strategy), each slotting in above as a new module.
- **Layer order is data, not hardcoded.** A single ordered manifest (low→high) is
  the source of truth; the CLI command table and the import-boundary test both
  DERIVE from it. Adding a layer = append to the manifest, no dispatch/test edits.
- The invariant is the only fixed thing: each layer imports strictly downward,
  never upward — count-agnostic, so it survives the stack growing.
- **Reach = triangular:** a layer may call ANY layer below it directly (not just
  the adjacent one). Less pass-through boilerplate as layers multiply; the
  dependency graph is a downward triangle. The boundary test forbids only upward
  edges, not non-adjacent downward ones.

### v1 built + FIRST DETERMINISM MEASUREMENT

Built the layered `arcg` stack (Layers 0-3) per the plan:
- `arcg/` package: `manifest.py` (layer order as data), `store.py` (substrate:
  session + determinism cache + snapshots), `layer0_protocol` (raw verbs, sole
  client importer), `layer1_intent` (move/interact/click/undo + look/diff),
  `layer2_state` (history/snapshot/restore/peek + budget meter), `layer3_memory`
  (note/notes), `cli.py` (dispatch derived from manifest).
- `tests/test_layering.py` enforces no-upward-imports + only-Layer-0-imports-client
  (derived from the manifest). `tests/test_consistency.py` covers history, budget
  cap termination, cache round-trip, and BOTH determinism verdicts (deterministic
  + nondeterministic fake). 23 tests pass. Old `tools.py` removed.

**MEASUREMENT (LS20, live, budget cap 15): post-RESET replay is DETERMINISTIC.**
Played `move left, move left`, snapshotted, diverged with `move right`, then
`restore` did full RESET + replay `[ACTION3, ACTION3]` and reproduced the cached
frame byte-for-byte → `DETERMINISTIC ✓`. So the bench property we hypothesized
(and the rulebook did NOT document) HOLDS for LS20, at least for this 2-action
sequence. This is the load-bearing assumption for the whole snapshot/restore
design — now it has one empirical leg. (Caveat: one game, one short sequence;
keep the restore-check on to catch any sequence/level where it breaks.)

Also confirmed live: `move left` = ACTION3 slides the 12-block left; budget meter
increments (1/15...5/15); `restore` cost 3 budget (reset+2 replays), reported;
`peek` spends 0 budget (cache-only); terminated cleanly under cap via `end`.

## 2026-06-25

### Upper layers named via the cognitive-architecture memory typology

Read `action-dag.md` and the Hypothesis Graph paper (june.kim). They are the two
upper floors of the stack, and the CoALA/Soar memory typology fixes their order:

- **Layer 2** already holds **working memory** (live session) + **episodic
  memory** (action trace + replay/restore). The determinism we measured is its
  replay substrate.
- **Layer 3 = pmem (procedural memory) = Action DAG.** Compiled goal→action
  decompositions: embedding filter (intent → subtree) over an HTN cache, LLM as
  JIT compiler on miss, write-back on success (= Soar chunking, the paper's own
  framing). Replaces the stopgap `note`/`notes` scratchpad — freeform notes get
  typed into pmem (how) and smem (what).
- **Layer 4 = smem (semantic memory) = hypothesis graph.** Falsifiable claims
  about game mechanics ("12-block=avatar", "ACTION3=left"), each a typed node
  bound to a trial, kill-condition edges, replay invariant. Runs trials via L2
  (snapshot/restore) + L1 (delta = the bi-abductive figure/ground diff we already
  built as `diff_grids`).

**Dependency subtlety, resolved (keeps the downward-only discipline):** pmem sits
below smem despite planning seeming to need mechanics-knowledge. No circularity,
because pmem-the-data-structure does NOT import smem. The Action DAG is a passive
filter+cache validated by the *environment oracle* (did the sequence work?), not
by querying smem. The semantic knowledge that informs a decomposition enters as
prompt context when the policy (top of stack) fires the JIT on a cache miss —
top-down injection, never an L3→L4 code edge. Both pmem and smem are graded by
the game, the un-authorable external oracle (the hygraph paper's active
ingredient — here it's free, the environment supplies every verdict).

### Collapse: old L1 (intent+perception) and L2 (state/determinism) merge

Perception, intent, and snapshot/restore are one concern — the agent playing and
tracking the game in game-terms; the determinism/replay is part of *how you
interact*, not a separate layer. So they collapse into one **intent** layer.

**Final 4-layer stack:**
```
0  wrapper   raw API verbs (only importer of ArcClient)
1  intent    move/interact/click/undo/look/diff + snapshot/restore/peek/history
             + budget meter  (working + episodic memory + the replay substrate)
2  pmem      Action DAG — compiled goal→action decompositions (procedural)
3  smem      hypothesis graph — falsifiable mechanic-claims (semantic)
```
Split is interaction substrate (0,1) under memory (2,3). Policy sits at the top.
Reach all downward/triangular: smem → intent + pmem; pmem → intent.
Code refactor (rename `layer0_protocol`→`layer0_wrapper`; fold `layer2_state` +
`layer3_memory` into `layer1_intent`) is PENDING — held while the architecture
keeps landing; v1 stays committed and green meanwhile.

### Two loops + the inquiry loop (methodeutics grounding)

The memory layers are stores; two processes move information between them, and
they're decoupled so the code stays a downward DAG even though the data flow is a
cycle.

- **Execution loop** (sync, fast): policy → pmem (cached skill) → intent (act) →
  wrapper (API). Each action pushes an episodic event.
- **Learning loop** (async, pull-based): an agent *fetches* epmem and cascades
  updates upward — **epmem → smem → pmem**. Episodic experience generalizes into
  semantic mechanic-claims (the inquiry loop), which compile into procedural
  skills (Soar chunking).
- **Cycle:** epmem → smem → pmem → action → epmem. Circular in data flow.
- **Cycle-breaker:** the `action → epmem` edge is **async** (fire-and-forget into
  an append-only episodic buffer; the learning agent fetches from it). Producers
  never sync-call consumers, so no upward import, no recursion. Event-sourced /
  blackboard decoupling; matches the hypothesis graph's append-only nature.

**epmem = episodic memory** (the action/perturbation trace + replay) lives in the
intent layer; smem reads it.

**The inquiry loop (the epmem→smem step) is methodeutics.** Read ch07 Origin of
Inquiry: the diff can't choose its own basis — *the goal frames the basis*
(purpose selects what to observe before any diff runs; the mechanic's six gauges
came from what she was fixing, not from the diff). Consequences for us:
- **pmem hands the perception basis down to intent.** The nested goal stack
  (win → complete level → learn mechanic → perturb+diff) sets, at each rung, the
  basis the rung below observes. ch07 maps this nesting onto HTN→Soar and links
  the Action DAG directly. So pmem→intent (downward): the goal selects which slice
  of the 64×64 grid is figure.
- The inquiry loop across methodeutics: ch04 diff / ch05 bi-abduction (the
  figure/ground primitive = our `diff_grids`), ch07 origin (goal frames basis),
  ch08 economy of research (which perturbation to spend budget on = our RHAE
  budget meter), ch09-11 trajectory / four-bins / kill-conditions (classify the
  response, generate the edge). That loop, run over epmem, writes smem.
- ch07's standing warning: a sharp frame is a sharp blindness. The goal that makes
  perception finite also makes it partial — the agent won't see what its current
  goal framed out. Worth remembering when a mechanic hypothesis stalls.

### Goal formation — the hard, ARC-AGI-3-specific problem

Read ch01 (the three-mode loop), ch07 (goal frames basis), ch08 (economy of
research). The loop (ch01) fires on a surprise; surprise needs a goal-framed basis
(ch07); ch07 dissolves cold-start with "a live purpose one rung down." **ARC-AGI-3
is the pathological case: no rung below the top goal.** You get only
`levels_completed up / WIN` and must INVENT the intermediate goals (avatar, exit,
what scores). That's ch07's basis *invention* (generation, not selection) — the
part no tradition gets for free.

**Reframe: two oracles, both free from the environment, very different rates.**
- *Mechanics* (smem node-type): "ACTION3 moves the 12-block left." Oracle = the
  **delta**. Dense (every action), cheap. Learns GOAL-FREE via undirected
  curiosity / prediction-error (ch07 reorganization). We already saw ACTION3=left
  fall out of the delta with no objective in hand.
- *Goals* (smem node-type): "objective = block onto the 9-token." Oracle = the
  **score / WIN**. Sparse (~once per level), expensive. Starved until the FIRST
  level-up; goal formation is one-shot abduction from the episodic trace of that
  first success ("what controllable config preceded the score tick?"). Before
  that, only curiosity.

**The crusher (ch08 under RHAE).** Goal abduction needs score events; score events
cost many actions; actions are the budgeted resource RHAE scores. So the
exploration that finds the goal tanks the efficiency it's graded on. ch08 is the
only move: every action a crucial experiment (Platt), max info-gain/cost
(GDE/Peirce), multiple working hypotheses (Chamberlin) so each step eliminates the
most. Economy of research is survival here, not polish — the budget IS the score.

**Architecture:** goals = smem node-type on the slow (score) oracle; mechanics =
smem node-type on the fast (delta) oracle. Witnessed goals compile smem→pmem into
the goal stack (ch07 nesting / HTN), which frames the basis intent perceives
against. Open goal-hypotheses stay in smem; the policy picks which to pursue by
economy-of-research. Goal formation rides the same epmem→smem→pmem cascade, just
on the slow oracle.

### The game model — placement (breaks the budget crusher)

We need to perturb a MODEL (simulate) instead of the real game, because real
actions cost RHAE. Decision: **the game model is smem read forward — not a new
store.** Witnessed mechanic-claims ARE a transition function ("ACTION3 → block
left"); simulating = applying them to a state to predict the next. Keeps it
auditable (every prediction traces to claims with replayable trials); a separate
learned simulator would be the opaque blob the hygraph paper argues against.

**Three modes (ch01) map onto model-vs-real, which sites the budget:**
- *abduction* — propose a mechanic from a real surprise.
- *deduction* — simulate the model (smem forward) → predicted next-state. FREE.
- *induction* — spend a real action to test the prediction. COSTS RHAE.
So most inquiry runs in free deduction (model rollouts); spend a real action only
where deduction is uncertain or confirmation is crucial — exactly what ch08 ranks
(max info-gain/action, measured against what the model already predicts). The
model converts "every experiment costs budget" into "spend induction only where
deduction is unsure."

**Two-tier model:** Layer 2 determinism cache (exact memo of VISITED sequences,
free, ground-truth) under Layer 3 smem (generalizing simulator for NOVEL states,
free, approximate). Cache hit → exact; miss → predict. The determinism work is the
model's ground-truth anchor.

**Imagined rollouts stay transient** (policy scratch), NOT written to epmem —
epmem stays the ground-truth replayable record (replay invariant: only real trials
are nodes). Simulated experience is deduction; it proposes candidates, but a claim
is witnessed only by a real-game induction. Real actions do double duty: progress
+ model validation (prediction vs real delta = kill/witness; a misprediction is a
surprise → abduction → refine smem → refine model).

### Imagination vs reality = the surprise engine

Comparing the model's prediction (imagination) against the real outcome (reality)
GENERATES the surprises that fire abduction (ch01). This is the hygraph paper's
active ingredient made concrete: model = what the agent believes, game = what is
true, **XOR(predicted, actual) = surprise = abductive trigger.** The model can't
author its own surprises (self-consistent → no surprise); the surprise must come
from reality, the un-authorable oracle — which is why abduction is the necessary
EXTERNAL operation.

- **Model as surprise-filter (the economy).** Abduce only on mismatch; a matched
  prediction just WITNESSES (raises credence on the claims it used, no new node).
  The agent thinks hard only when reality violates its model — expected outcomes
  suppressed as noise, surprises surfaced as figure. Cheap under RHAE.
- **Two basis-providers, both placed.** Goal (pmem) frames RELEVANCE (what to look
  at, ch07); model (smem) frames EXPECTATION (what to predict). Surprise =
  relevant ∩ unexpected: the goal picks the variables, the model picks the
  surprising values among them.
- **Determinism makes every surprise clean signal.** Because the game is
  deterministic (measured on LS20), predicted ≠ actual means the model is WRONG,
  never noise. Every surprise is a real model error worth abducing on. This is why
  the determinism measurement was foundational: it makes prediction-error
  noise-free.
- **Economy of research, sharpened (ch08):** spend a real (induction) action where
  you most EXPECT a surprise — where the model is least confident. Confirmed
  predictions waste budget; mismatches are maximally informative. Uncertainty
  sampling, with the model supplying the uncertainty.

### The XOR engine: methodeutics primitives + the abductor, ported

Read the primitive progression (ch04 diff / ch05 bi-abduction / ch06 tri-abduction)
and mapped the abductor tool (documents/abductor) to rebuild a version for the game.

**Primitive progression → game:**
- *unary diff* (ch04): before/after → figure/ground. = our `diff_grids` (figure =
  moving object, ground = static board).
- *bi-abduction* (ch05): infer footprint + frame + precondition WITHOUT choosing
  the snapshot. Frame rule → learn an action's effect locally on the object it
  touches; it composes anywhere on the board (object-centric, compositional
  mechanics). Also infers the precondition ("needs empty space left").
- *tri-abduction* (ch06): shared start + two perturbations → causal edge (Mill's
  method of difference). = controlled experiment for CONDITIONAL mechanics
  ("left UNLESS blocked"). **Payoff: determinism + snapshot/restore IS the
  tri-abduction substrate** — same start guaranteed, clean causal edge, impossible
  in a stochastic game. Layer 2 was the right first build.

**What the abductor actually is** (src map): a set-reconciliation XOR engine +
hypothesis graph.
- core: `reconcile(a,b) → (a_only,b_only,decoded)` — symmetric difference of two
  ACCEPT-SETS via an IBLT, O(d) in the difference size, without materializing
  either set. The ch04 diff made cheap.
- enumerate (fixpoint-closed case space) / calibrate (baseline accept-set from a
  known-good oracle, once) / gate (`reconcile(believed, truth)` → fp/fn, exit 0
  agree / 10 disagree).
- diff-the-diff = checking analogue of tri-abduction (Zilberstein OSL 2024): two
  oracles, directional, routes collapse_WIDE vs collapse_NARROW (the Verus
  too-wide/too-narrow axis).
- `HypothesisGraph`: abduce/kill/witness/from_kill/probe; `probe()` fuses
  abduce→test→classify, returns counterexamples that name the next hypothesis.

**Port to ARC-AGI-3 (nearly 1:1):** case space = (object, action, local-context)
via bi-abduction footprints; candidate accept-set = the MODEL's predictions (smem
forward, free); baseline = the real GAME; `reconcile(predicted, actual)` = the
SURPRISES; agree→witness / disagree→kill+abduce; diff-the-diff = conditional
refinement.

**The one crucial adaptation:** the abductor's oracle is free+total (computes over
all cases at init). OURS is live+expensive (each case = an RHAE action). So the
baseline can't be materialized — replace "compute oracle over all cases" with:
(1) FREE+partial: the determinism cache (visited pairs → true outcome via peek;
reconcile over those is free); (2) EXPENSIVE+sampled: spend a real action only
where ch08 says (model least confident = max expected surprise).

**Elegant consequence:** IBLT cost = O(d), d = #surprises. As the model learns the
surprise set shrinks, so the XOR engine gets cheaper exactly as the agent gets
better; cache reconciles are free; budget is spent only to sample reality where
the gate is uncertain.

### epmem storage: whole + patches (the world is small)

A frame is ~4KB (64x64) and logging is INTERNAL (free — only real actions cost
budget), so store epmem BOTH ways, no tradeoff:
- **whole** = full frame at a step. Exact, replayable, peekable; the snapshot/
  restore + tri-abduction same-start substrate. = the determinism cache (wholes
  keyed by sequence) — already built.
- **patch** = the delta (figure from `diff_grids`). Tiny; the native unit of the
  XOR engine (XOR(predicted_patch, actual_patch) = surprise) and of the cons
  FILTER (keep surprising patches, drop syndrome-zero). Already built.
Inter-convertible, exact under determinism:
  whole_{t+1}=apply(whole_t,patch_t); patch_t=diff(whole_t,whole_{t+1});
  whole_n=replay(whole_0,action_seq).
This is compress-and-unfold's centers/edges split as a storage layout: wholes =
centers (static, write-once, fixed points), patches = edges (live, generative).
It's git for game states: wholes = checkouts, patches = commits; small world makes
checkouts cheap enough to keep both. Consequence: **epmem can be EXHAUSTIVE** —
log everything (whole, patch, prediction, surprise, score), decide what to keep at
CONSOLIDATION time (where cons puts the decision), not at write time. Budget lives
only at the inhale (real actions); the record is unlimited.

### Temporal diffs = edge detection; the action is the operator

Patches are edges in TIME the way Sobel/Canny are edges in SPACE; the ACTION is
the operator that produces them. `diff_grids` = temporal edge detection (figure =
edge, ground = flat). This answers the object-ontology question:
- **spatial edges** (within a frame, region boundaries) → OBJECT PROPOSALS
  (connected components).
- **temporal edges** (across frames, action-driven) → MECHANICS.
- they cross-validate: a spatial edge proposes a region; temporal co-movement
  WITNESSES it ("these cells moved together → one object"). Objects are abduced
  from spatial structure, witnessed by co-movement — abduce→witness one floor down,
  the lowest tier of smem. (The 12-block: shared boundary AND moves as a unit.)

**Structure-from-motion.** Vision recovers 3D structure from how things move across
frames; the agent recovers the ENGINE's structure from how the grid moves across
ACTIONS. The action is the controlled probe (like varying viewpoint/lighting).
Tri-abduction = controlled structure-from-motion (same start, two probes, the
divergence localizes the cause).

**Edges are the compression; the surprise is an edge-of-edges.** Patches (temporal
edges) are the information-dense unit; the flat ground is redundant — cons's filter
= keep edges, drop flat (the exhale, as edge detection). The surprise =
XOR(predicted edge map, actual edge map) = a SECOND-ORDER edge = the abductor's
diff-the-diff; wide/narrow = predicted edge too big / too small.

Perception stack reads as a vision pipeline, each stage the same `diff` primitive
at higher arity (ch04→05→06): raw frame → spatial edges (objects) → temporal edges
(mechanics) → structure-from-motion (engine) → second-order edges (surprises).

### Undo = cheap branch; git as the epmem substrate

**Undo (ACTION7) is the local-branch operator.** O(1) (1 action) vs reset+replay's
O(N). For tri-abduction at the frontier ("same start, vary the last action"):
`act A → undo → act B` = two siblings from one parent for one undo. Both cost
budget (undo is a real action), but undo is the cheap local branch, reset+replay
the arbitrary jump. The exploration tree is built mostly from undo.

**Git as epmem substrate (fits deeply, easy to impl).** Git's object model IS the
monotone write-once semilattice compress-and-unfold demanded:
- immutable objects = write-once centers (the one axiom)
- content-addressing = dedup = idempotent semilattice merge (same state via
  different sequences → same tree hash, the diamond collapses for free)
- `git diff` = patches (temporal edges); commits/trees = wholes (deduped)
- branches = exploration tree (undo-branches); `git checkout` = free model-side
  restore; tree-hash compare = exact free determinism check
- Merkle DAG = provenance / replay
Impl: temp/bare repo, one commit per step (frame blob, action in message). ~10ms/
commit is nothing vs game-API + LLM latency (seconds). FREE WIN: inspectability —
`git log` = action history, `git diff` = each temporal edge, `git branch` = the
exploration tree. Watch the agent think by browsing the repo.

**Two layers, two guarantees** (matches the hygraph paper's Portable-Agent-Memory
vs hypothesis-graph contrast): git-epmem = INTEGRITY of the record (content-
addressed, tamper-evident, what happened); smem = WARRANT of the knowledge
(witnessed mechanics that survived trials, what's true). Model synthesized from the
former, validated into the latter.

### CORRECTION: each named structure is only the CACHE of its layer

The data structures (git-epmem, hypothesis graph, Action DAG) are only the
consolidate-RESIDUE of their layers. Each layer is a full **perceive → filter →
attend → consolidate** cycle (the cons operator); the cache is what falls out the
end. The stack is a tower of cons cycles, not a tower of stores.

| layer | perceive | filter | attend (abductive leap) | consolidate → cache |
|---|---|---|---|---|
| wrapper | raw API frame | parse/validate | — | frame + cookies |
| intent/epmem | frames | temporal diff: keep edges, drop ground & syndrome-zero | object co-movement; goal-framed salience | git-epmem (transposition table) |
| smem/model | epmem surprises | drop model-explained | abduce mechanic; wide/narrow; ch08 economy | hypothesis graph + engine |
| pmem/skills | smem + goal events | drop one-off seqs | which recurring seqs = decompositions | Action DAG |

What we "built" = pieces of specific layers' cycles: `diff_grids`/render = intent
perceive+filter; `reconcile`/XOR = smem filter; ch08 = smem attend; cons operator =
each layer's consolidate.

- **Self-similar: cons cycles all the way down.** Same perceive→filter→attend→
  consolidate at every layer over different inputs (compress-and-unfold's spiral at
  every scale; the laws name no substrate).
- **Division of intellect repeats per layer:** ATTEND is the abductive leap
  (model/LLM, cons's "human decision point"); perceive/filter/consolidate are
  mechanical (harness). The hygraph "model reasons, harness gates" is the shape of
  EVERY layer — a thin band of abduction wrapped in mechanical P/F/C.
- Sharpens budget optimality: a real action is spent only inside an ATTEND step
  where filter couldn't drop it and cache+model couldn't supply it.
- Build restated: each layer = the cons quadruple + its cache. git-epmem spike =
  the intent layer's consolidate+cache; perceive/filter (edge detection) exist;
  ATTEND (salience / object co-movement) is the piece still owed there.

### CONSOLIDATE is left blank — the agent handles all cache updates

Decision: don't formalize consolidate yet — its shape is unknown (it's the UNSOLVED
morphism: cons/functor-wizardry say "consolidation remains manual"; hygraph says
"the model writes, the harness gates"). Leave the slot empty; the AGENT performs
all cache updates directly. perceive/filter are mechanical and defined; ATTEND and
CONSOLIDATE are the agent's, with consolidate unconstrained.

**Why safe, not reckless:** convergence comes from the cache STRUCTURE, not the
consolidate operator. compress-and-unfold: a monotone, write-once, content-
addressed semilattice climbs to an order-independent LEAST FIXED POINT — independent
of the writing policy. So enforce the cache laws MECHANICALLY (write-once centers,
fire-on-presence, content-addressed dedup, collapse-and-rebuild on rot) and a loose
/ even chaotic agent-driven consolidate STILL CONVERGES. The lattice forgives a
sloppy writer; the structural axiom does the work the operator's shape would.
> discipline lives in the cache, not in the operator.

Split per layer: mechanical & defined now = cache + laws, perceive, filter
(edge detection, reconcile/gate); agent, free, unspecified = attend (abduce) +
consolidate (write into the law-enforcing cache).

**This is cons applied to itself:** leaving consolidate to the agent AND logging it
is the cons process pointed at building consolidate. Run manual (agent-driven),
record writes, watch the recurring shape, extract the operator later (the ratchet).
Run cons to discover cons. The blank slot is where the next cycle finds its pattern.

### The agent is a quad-paradigm system (four-schools-of-programming)

four-schools: the QUAD (imperative+functional+declarative+actors) IS the
cognitive-architecture problem as a programming language (Soar/ACT-R hand-wired all
four; LLM stacks glue them). Our agent maps onto all four:
- **Imperative** = real-game actions (mutable world, "press the button", the
  inhale). Irreducible: can't perceive your way out of acting.
- **Functional** = the model/engine (pure `step`, content-addressed — our decision).
  Irreducible: a pure transition has no inside → replayable, content-addressable.
- **Declarative** = goals (scoring constraint) + smem (claims & kill-conditions as a
  relation network). Irreducible: constraints/relations, what not how.
- **Actors** = the async layers (the stretch goal). Irreducible: isolated cognition,
  message-passing via caches.
Async-layers isn't a side note — it's the 4th school completing the quad.

**Seams = our integration points** (each paradigm's complement patches its seam):
- *Func+Imp = Kleisli over effect monad* (Moggi/Wadler): pure model can't touch the
  world (data-processing inequality) → real action = the effectful boundary. The
  inhale/exhale IS Kleisli composition / the IO monad. The core.
- *Func+Actors = Unison* (content-addressed pure fns across actors; "pure-vs-stateful
  is a deployment concern"): our functional model + git + async layers. Validates
  "async = deployment change, not redesign" — that's Unison's defining property.
  Prior art for our substrate.
- *Decl+Actors* = the post's LEAST-settled pair, "where multi-agent LLM lives": our
  async layers orchestrated by the declarative consolidation/monoid laws. Our
  stretch goal sits on this exact frontier.
- *Decl goal patched by procedural pmem*: goal = what scores (declarative), Action
  DAG = how (imperative escape hatch).

**Assignment rule:** each component uses the paradigm whose "irreducible because"
matches its nature. We derived each corner separately; four-schools says they're one
figure. We're building the quad deliberately, at the named seams.

### SERIAL output → no actor model (simplification, retracts the async buffer)

The single game session is inherently SERIAL: one guid, one current state, one
action at a time, one frame back. The budget-bearing channel (real actions) can't be
parallelized within a session, and there's all the idle time wanted between actions
to run the cascade synchronously. So: no concurrency to exploit, drop the actor
runtime. Architecture = a SERIAL LOOP:
```
per step: perceive frame → run cons cascade synchronously (epmem→smem→pmem) →
          decide → emit ONE action (serial output) → repeat
```
Retractions (over-engineering for a serial system):
- **The async epmem buffer is unnecessary.** The circularity was only in the CODE
  dependency graph, already handled by downward-only layering — not by async. The
  cycle is cut by ITERATION: epmem written at end of step N, read by step N+1's
  consolidation. Sequential iteration decouples without message-passing.
- **Synchronous consolidation is correct, not a fallback.** Every real action is too
  budget-precious to spend on stale knowledge → fully consolidate before acting.
  Background consolidation buys nothing when the loop gates on fresh knowledge.
Keep vs drop:
- KEEP the cache LAWS (write-once, monotone, content-addressed dedup): give
  convergence + forgive loose consolidate, independent of concurrency; leave the
  door open for optional cross-SESSION (multi-guid) parallelism later (CRDT = free
  lock-free).
- DROP the actor RUNTIME (mailboxes, async message-passing, concurrency safety).
four-schools: quad → TRI-paradigm (imperative actions, functional model, declarative
goals/smem); the actors corner degenerates to a SINGLE actor = the serial loop (one
actor = a sequential program). Multi-actor stays the stretch goal — serial output
means it buys nothing now.

### NEAR-INSTANT execution → no explicit queues

The harness machinery (perceive/filter/consolidate-writes, cache ops over a small
world) is near-instant, so no backlog ever forms → nothing to buffer → no explicit
queues. Queues earn their keep only on backpressure (producer > consumer), async
decoupling (dropped), or batching (per-step is fine) — none apply.

Simplifications compose to the minimal shape:
- serial output → no actors; near-instant execution → no queues
- ⇒ a synchronous STRAIGHT-LINE LOOP = function composition
  `perceive ∘ filter ∘ attend ∘ consolidate ∘ decide` then act. Reinforces the
  functional decision: no queues means the pipeline IS composition.

Keep vs drop (sharp distinction):
- KEEP the epmem LOG (git) — a persistent RECORD/cache, not a work-queue.
- DROP work QUEUES (mailboxes, message buffers, backpressure) — flow-control with no
  flow to control.
Only slow boundaries left: real action (API ~s) and LLM attend/abduce (~s) — just
BLOCKING calls, which is correct (block, act on fresh knowledge, every action
budget-precious). Slow-synchronous-few beats fast-buffered here.

YAGNI in the right direction: small world + serial session + near-instant harness ⇒
the simplest shape (synchronous loop of pure-ish functions over a git-backed log) is
the CORRECT design, not a shortcut. Actor/queue machinery would solve problems this
system doesn't have.

### Exact/Boolean regime, not statistical (Peirce, via determinism)

Peirce was doing Boolean logic (extended Boole: quantifiers, algebra of relations,
Peirce's law) and critiquing the "fallacy of syllogism" — deduction is ANALYTIC,
adds no content; the ampliative work is abduction. He wrote it in 1878, presaging
and dunking on statistical inference decades before Fisher/Neyman.

Consequences for the agent:
- **His syllogism critique = the data-processing inequality, in logic, 70 yrs before
  Shannon.** "Deduction adds nothing" ≡ "no computation on what you hold raises what
  it tells you about the world." So simmer (deduction/simulation) is Peirce's
  syllogism: exact, free, knowledge-NEUTRAL. The fallacy = mistaking a simulation
  for discovery. Only the real action (abduction grounded in the world) adds content.
- **Determinism puts us in the EXACT/BOOLEAN regime — statistics is a category error
  here.** Noiseless channel → every op is Boolean, not statistical:
  - a mechanic-claim is a Boolean predicate (moves-left? yes/no, exactly);
  - XOR/reconcile is literal set difference (IBLT = Boolean set logic, not inference
    under noise);
  - the kill is EXACT — one counterexample refutes (Popper/Peirce, not Fisher); no
    p-value, no power, no confidence interval;
  - "credence" = the hygraph's three Boolean states (open/killed/witnessed); the
    mode-cap is a convention, not a probability.
- Statistics only re-enters if the game is STOCHASTIC (noisy channel → redundancy +
  sampling = the error-correcting code, compress-and-unfold's high-noise branch).
  Determinism keeps the whole agent in the algebra of logic.
- **Design line (what NOT to build):** an exact-logic engine, not a statistical
  learner. No probability estimation, no confidence thresholds, no
  sampling-to-significance. Boolean status + exact kills.

### Budget optimality: never query the same state twice

Content-addressing + determinism = a STATE-level transposition table:
`(state_hash, action) → outcome`, queried at most ONCE EVER. State identity is
path-independent (same content → same hash), so any sequence reaching a state
inherits every transition already observed there. Pay once, own forever.
- Stronger than the sequence cache: reconvergent states COLLAPSE. ARC-AGI-3 is
  full of reconvergence (left·right = identity, undo loops, reversible moves) —
  every diamond collapses to one node, so you never re-explore a state however you
  reached it. Big free saving the sequence cache misses.
- Two-tier "never pay twice": (1) exact (content cache: never re-query an observed
  transition = recall); (2) generalized (model: never query a predictable
  transition = deduction). A real action is spent ONLY on transitions both NOVEL
  (cache miss) AND SURPRISING (model miss) — the intersection, the absolute
  minimum.
- This is compress-and-unfold's data-processing inequality made operational:
  content cache = the recall floor, model = the derivation floor, budget buys only
  what sits above both (a new dimension only the world can supply).
- **real-action spend = |novel ∩ surprising transitions|** = the minimum
  information the agent must pull from the channel. Every reconvergence and every
  deducible step is free. As efficient as the physics allows.

**Rebuild = `reconcile` (IBLT, port nearly verbatim) as the surprise core +
hygraph as smem + enumerate via bi-abduction footprints + calibrate against
cache-free + budget-sampled reality + gate = surprise → abduce + diff-the-diff for
conditional refinement.** Proven structure, oracle swapped free-total → live-sampled.

### Common engine across levels + functional model (transfer settled)

Observation: level structure is repetitive → the TRANSITION FUNCTION is invariant
across levels (likely shares primitives across games); only LAYOUT + GOAL change.
Factor the model:
```
model = engine(step: State × Action → State)   ← learned once, transfers across levels
      + level(initial_state, goal_predicate)    ← re-perceived per level
```
Transfer scope (closes the open question):
- determinism cache (L2): per-session, exact, NO transfer.
- engine/mechanics (smem): per-GAME, layout-independent (frame rule), transfers
  ACROSS LEVELS. Object-centric is WHY it transfers.
- goals: per-level (target shifts); goal-TYPE may recur.
Budget: pay to learn the engine on level 1, cheap thereafter — mirrors humans.
RHAE scores each level vs a FIRST-TIME human, so engine-learning on early levels is
already priced into the baseline; level-1 exploration isn't penalized as feared.

**Functional model representation (decision):** the learned engine is a PURE
functional program — `step(state, action) → state'`, immutable state, composed
from per-object pure rules (each mechanic-claim = a pure function). Forced by what
we built, not stylistic:
- determinism IS purity (game = pure fn of its action sequence);
- frame rule IS functional locality/composition (engine = fold of per-object rules);
- snapshot/restore = immutable values (restore = reuse, no mutation to undo);
- replay invariant = referential transparency (exact replay by construction);
- transfer = layout-independence (functions bake in no positions).
Makes the abductor port EXACT: candidate goes from `Callable[[int],bool]` to
`Callable[[State,Action],State]` (the synthesized engine), reconciled against the
game — same gate, one type wider.

**Framing:** the agent does FUNCTIONAL PROGRAM SYNTHESIS of the game engine —
abduce per-object rewrite rules, compose into `step`, differentially test against
the live game (the XOR engine), under budget. Same thesis as "Executable World
Models for ARC-AGI-3" (world model = executable code); functional is the form
that's pure, composable, replayable, transferable.

### Built so far (before this planning round)
- REST client (OpenAPI-faithful), perception (grid render + frame delta),
  random baseline, programmatic Claude policy (`arc3`), agent-facing `arcg`
  tools (`games/start/look/act/note/status/reset/end`), session persistence with
  AWSALB cookie carryover (bug fixed: httpx CookieConflict on duplicate
  GAMESESSION → iterate the jar). 14 offline tests pass.
- Live: random agent scores 0; Claude policy drives real actions via
  subscription; `arcg` plays LS20 end-to-end.

### Milestone 0: `objects` — the one unambiguous build (committed 6903641)
Brief was "build everything that's unambiguous." The plan gates jotter/arbor/
simmer/dagger behind the ratchet (codify only when the in-head version visibly
breaks), leaves the driver name Open/TBD, and the arcg→piper rename is a real
decision (the target piper surface pushes move/snapshot/notes into other modules;
touches the package dir, console-script, AGENT.md, test_layering). So none of those
are unambiguous. The ONE thing that was: Milestone 0 step 1's piper checklist —
"act/look/diff/snapshot/restore + undo + objects" — had everything but `objects`
(undo was already wired via layer1_intent.undo/ACTION7).

Built `arcg objects` = connected-component spatial-edge perception (the figure/
ground primitive the plan calls "edge detection"):
- `perception.find_objects/GridObject/describe_objects` — flood-fill segmentation
  (4-conn default, 8 via --diag), modal colour treated as background and excluded
  (--with-bg keeps it). Written in the diff_grids/Delta style.
- `layer1_intent.objects` — free perception verb beside look/diff (reads the stored
  frame; no action, no budget). Names "the 12-block" instead of raw cells.
- Magnitude-honest output (caps at 40, "+N more"); doesn't judge — background is
  excluded but recoverable, nothing hidden (CLI convention #1).
- 5 new tests; 27 pass. Smoke-tested on a synthetic LS20 grid: background 4 auto-
  excluded, UI bar (5) / avatar block (12) / two scattered 9-tokens each surfaced.

Harness note: the project's autoenv hook prompts y/n/d on `.env` for every `cd`
into the repo and blocks non-interactive shells (it ate a heredoc commit message's
stdin). Use `git -C <path>` / absolute paths, no `cd`.

Open (unchanged, by design): driver name; arcg→piper rename; explainer prompt
(partly served by AGENT.md — the dedicated "map" version per §Onboarding is next if
wanted). jotter/arbor/simmer/dagger stay deferred until observed to break.

### jotter commit message = the reason, as a typed ref into arbor/dagger (spec)
Refining the action-provenance track (jotter still deferred; spec only). The git
commit message is JUST the reason the action was taken — not a restatement of the
action (that's commit metadata) and not the resulting state (that's the tree).
Ideally the reason is a typed ref: `arbor:#4` (the claim this action tests) or
`dagger:<id>` (the plan node it executes), so the action edge walks back into smem/
pmem instead of being dead prose. Free prose only for undirected probes.

Clean distinction so the two arbor-touching tracks don't blur: a commit MESSAGE
refs a claim to mean *this action tests it* (motivation, forward); a git NOTE refs
the same claim to mean *it is believed because of evidence E* (justification,
backward). Same node, opposite provenance direction — `jotter why` walks either way.
CLI sketch gains `[--for arbor:#<id>|dagger:<id>]` on commit. PLAN.md updated.

### simmer synthesis: abductor writes the game, jotter history is the test corpus
Settling how code gets into simmer (still deferred; spec). The pipeline closes:
jotter (tests) → abductor/arbor (gate+compose) → simmer (`step`). Key moves:

- **jotter's grounded-facts track IS the test suite.** Every recorded (s,a)→s' is a
  golden test; `piper ⊕ simmer` is the test runner. A mechanic-claim's abductor
  `--trial` = replay the corpus through the candidate `step`; `--kill-if` = mispredicts
  any covered transition. Gating is free/deductive against history; piper is touched
  only to GROW the corpus with novel transitions.
- **Determinism licenses the Boolean gate.** Game = pure fn of its action sequence
  (measured LS20), so one counterexample is a definitive kill — no thresholds, no
  statistics. Why the write-once abductor is the right tool, not a statistical fitter.
- **Per-object granularity → surgical kills.** A counterexample kills only the rule
  for the object the diff bbox touches; `from-kill` writes the successor, gated against
  the FULL corpus (strictly dominates → monotone climb up the semilattice). The kill-
  edge records which transition broke it = belief-provenance lineage, replayable.
- **Overfitting is avoided BY the abductor** (the user's point), no held-out split
  needed. A lookup/memorizing rule is the maximally-overfit claim and dies first: the
  next novel (s,a) has no entry → mispredict → kill. Witness credence accrues only on
  unseen transitions (off-training-set by construction); from-kill forces generalizing
  successors. Live novel transitions = a continuous falsification feed (Popper).
- **Division of intellect holds:** abductor gates+composes (`arbor engine` folds live
  claims into `step`), does NOT invent — the candidate rule body is the agent's
  abductive leap from the red diff. Later the abductor could enumerate candidates if
  the agent's proposals get rote (ratchet step, not now).

Lightest first build when simmer is unratcheted: `simmer compile` (load rules → step)
+ `simmer test` (replay jotter corpus, per-transition verdict like restore's
determinism check). One hand-rolled `step`; factor into per-object rules on sprawl; a
rewrite-rule DSL only when raw Python rules get unwieldy. Claims keyed by id (body may
be a source string) so arbor stays a mergeable semilattice without the DSL yet.

### Goals/actions: a new hypothesis TYPE, and a two-root planning graph (spec)
Working through what's genuinely new in ARC-AGI-3 vs prior abductor work on
engineered systems: there, hypotheses were about MECHANICS ("is the world like
this?", type *function* s,a→s') and the system defined success. Here success itself
is hidden, so two more things become objects of hypothesis:
- the **goal** — type *predicate* s→bool (what state wins)
- the **action-as-means** — type *path/program* (which action advances the goal)
Shift from hypothesizing *is* to also hypothesizing *what to want* and *how*. (Same
action, two questions: action-as-effect = mechanic; action-as-purpose = plan.)

**Three hypothesis types ↔ three gates (the symmetry that keeps it in the abductor):**
- mechanic → gated against jotter's TRANSITION track (state deltas). Dense, exact
  (determinism → Boolean kill).
- goal → gated against jotter's SCORE track. A candidate goal_predicate is killed if
  its true-flips don't align with recorded score increments. Same write-once abductor,
  different column. Asymmetry: positives are SCARCE (few score events) but negatives
  ABUNDANT (every non-scoring state must be excluded). So ruling out wrong predicates
  is easy; GENERATING the right one from 2-3 positives is the hard part — where the LLM
  prior is load-bearing (games want: reach exit / collect / align). Mechanics you
  brute-force; goals you must guess well. This is why the reasoner must drive, not code.
- plan → gated against simmer (does the decomposition reach the goal in imagination?).

**Two roots = two inference directions (the planning graph).** dagger is two sources
growing toward each other:
- 'win' top-down = ABDUCTION: regress goal → subgoals (guess, sparse, score-gated),
  predicate space. Frontier of *what I need to make true*.
- 'act' bottom-up = DEDUCTION: push actions forward through mechanics → reachable
  states (free in simmer, transition-gated, dense), state space. Frontier of *what I
  can make true*.
The PLAN is where they meet: a reachable state satisfies a leaf subgoal (bidirectional
/ means-ends). Deduction is free → expand act-up hard, keep win-down shallow. arbor is
the SHARED ALPHABET both are spelled in (act-step = a witnessed mechanic; win-entail
checked through mechanics), NOT a third root. Both JIT (act-up from current state,
win-down on miss).

**Failure-to-meet is a router, not a dead end:** nothing reachable satisfies a subgoal
→ re-abduce the goal; subgoals unreachable → spend piper to learn the missing mechanic;
children achieved but parent won't fire → from-kill a better decomposition (this is the
delayed/conjunctive credit-assignment hazard surfacing — score-jump cause may be
upstream, e.g. a key grabbed 10 steps ago; trace via jotter's belief-provenance cone).

Composition algebra (matches the monoidal contract): goal conjunction = commutative
idempotent meet-semilattice (= the merge law); sequence = non-commutative action
monoid. Peirce triad closes: abduce=win-down, deduce=act-up, induce=arbor's witness.
PLAN.md "### goals and actions meet in the middle" added. Still spec; dagger deferred.
