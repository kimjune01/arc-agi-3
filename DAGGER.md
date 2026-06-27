# dagger — loose prose typing

The Action DAG, typed in prose first. This is the **soft-typing** pass PLAN.md calls for:
write the structure and its one invariant as English a reasoner can check by judgment and
by running simmer, **not** a type system. Formal typing (a subsumption engine, a condition
DSL) is deferred until prose visibly goes off the rails. Until then the differential test
and execution-in-simmer are the only enforcement, and that is on purpose.

Prior art and the longer argument live in PLAN.md (§composability, §two-roots) and the
[Action DAG](https://june.kim/action-dag) post (HTN cache + embedding filter, JIT-on-miss,
write-back-on-success). This file is just the **typing**: what a node is, and the one
invariant that says a decomposition is correct.

## The node is a morphism

A node is **perspectival**: a goal from above, an action from below. Every node is both —
the same object is "what I want true" to its parent and "a thing I do" to its children.

That duality is a morphism. From above a node is its **postcondition** (the predicate it
makes true, its codomain). From below it is a **transformation** (it carries one state to
another). So the DAG is a diagram in a category whose objects are states (or the predicates
that name sets of states) and whose arrows are nodes. A leaf is a primitive arrow (an API
call / a piper action); an interior node is an arrow that *factors* into a composite of its
children.

This is the Winston move: **the right representation exposes the constraint.** Pick "node =
morphism" and the correctness condition for a decomposition stops being vague ("the children
should accomplish the goal") and becomes a single mechanical check — *does the diagram
commute*.

## The initial DAG: prepopulated with its two boundaries, nothing between

The DAG is born with **exactly its two roots and no middle**:

- **apex:** one childless compound node, **`win game`** — the goal. Childless = undecomposed; its
  decomposition is grown JIT/abductively (win-down regresses it into subgoals on miss), never
  authored up front.
- **base:** one **leaf node per primitive input** the game exposes — its action alphabet
  (`ACTION1`…`ACTION7`, or whatever the frame's `available_actions` reports). These are the only
  things the agent can actually *do*; act-up composes from them.

Everything in between — the subgoal decomposition descending from `win game`, the composed
reachable-state nodes ascending from the primitives — is **emergent**, grown on demand where the
two roots meet (see §the-two-roots). So the DAG's *boundary conditions* are fixed and its bulk is
learned.

This is also what makes the [dual-provenance invariant](PLAN.md) (every action points to an
action node and a hypothesis node) satisfiable from move 0: the **action-node leaves already
exist** at init for any action to point at, and **`win game`** is the root every subgoal
eventually hangs under. The first actions are bare primitive leaves testing open hypotheses;
decomposition fills the middle as the agent learns what achieves the goal.

## The one invariant: a decomposition is a commuting factorization

A node `g` with children `c1..cn` is a **valid decomposition** iff composing the children
recovers the parent:

```
compose(c1..cn) ⊨ g
```

Decompose and compose are inverse. Exhaustiveness *is* the round-trip fidelity: factor `g`
into children, recompose them, and you must land back at (something that entails) `g`. A
decomposition that loses information is a factorization that doesn't commute.

`compose` has two modes, both already in the monoidal contract:

- **sequence** — ordered, the **action monoid**. `c1 ; c2 ; … ; cn`. Identity is the no-op;
  associativity is "grouping of steps doesn't matter." Non-commutative: order is load-bearing.
- **conjunction** — unordered, the **meet-semilattice**. `c1 ∧ c2 ∧ … ∧ cn`. Commutative,
  idempotent, this is the cache **merge** law. "Achieve all of these, in any order."

A node declares which mode its children are in. (AND-node = conjunction; a recipe = sequence.
Winston's OR — alternative decompositions — is not a compose mode; it's *several* candidate
children-lists for the same `g`, the planner picks one.)

## Composition is codomain-meets-domain (pre/post matching)

Two nodes compose in sequence iff the first's postcondition satisfies the second's
precondition:

```
A ; B   is well-formed  iff  post(A) ⊨ pre(B)
```

That is exactly the categorical condition (arrows compose when codomain meets domain), and
it is the **pre/post matching** PLAN.md calls the connective tissue of the two roots. Nothing
new to build for it: pre and post are prose, `⊨` is a judgment.

## Soft typing: pre/post are prose, `⊨` is judged, the check is execution

- **pre / post are English strings**, attached to a node. "avatar adjacent to the lock",
  "carried pattern matches the lock", "token collected". No DSL.
- **`⊨` (entailment / subsumption) is the reasoner's judgment**, optionally sharpened by
  simmer: "does *block left-aligned* satisfy *block adjacent to wall*?" The LLM answers; if
  it is unsure, run it in simmer and look.
- **The invariant is TESTED, not proven.** To check `compose(children) ⊨ g`: achieve every
  child in simmer (free), then check whether `g`'s goal predicate fires. Fires → exhaustive
  for that instance. Doesn't → the residual is localized (which parent predicate is still
  false), and that gap *names the missing child*. `from-kill` the decomposition with it.
  This is the "children achieved but parent won't fire" router: a non-commuting diagram, and
  the non-commutation points at the repair.

Soft typing is safe because a wrong prose match costs a wasted simmer rollout, never a broken
plan — execution verifies. So the reasoner is *allowed* to be sloppy, and we learn whether
pre/post composition is even the right frame before building any machinery for it.

That safety holds only while the match stays on the predicate. A tolerant `⊨` may *propose* a
composition edge; keep it away from dedup and from any recursive abstraction. Dedup stays exact
(content-addressed, grid→grid, with no correspondence to judge), so a wrong proposal costs one
rollout and dies. Were the loose match allowed to decide node identity, one misjudgment would
merge two incompatible methods and corrupt the cache, a failure execution can't catch (it
verifies a single rollout, not the equality of two nodes). Matcher for the predicate; exact
equality for identity. The real cost in the predicate check is object correspondence, so keep
the abduced predicate language bounded (DL-lite: typed objects, unary/binary relations, bounded
counts and spatial relations) before the `⊨` judgment quietly becomes subgraph matching.

## Interface (outer): committed contracts, judged interior

The verb set and its *algebraic* contracts are fixed by the cache laws and the morphism. The `⊨`
decision procedure and the node's reliability schema stay judged/deferred (§soft-typing,
§deferred). So this commits the outer shape and names two holes rather than filling them.

**Node** = the morphism. Fields: `post` (prose goal it makes true, its codomain), `pre` (prose
applicability, its domain), and a body that is either a `leaf` (one primitive action token) or a
`compound` (`children` + `mode ∈ {sequence, conjunction}`). `status` carries the write-once
verdict (`open → live | killed`) and is OUTSIDE the identity key, so a kill never rewrites the
ref. Identity is the content-address over the NORMALIZED-EXACT remaining fields, never a matcher
call.

| verb | contract | law |
|------|----------|-----|
| `init <actions>` | seed = apex `win game` (open) + one leaf per action | determined, no freedom |
| `get <id>` | resolve a `dagger:<id>` ref to a node, or MISS | total; MISS is data, not error |
| `plan <goal>` | hit returns a cached decomposition; miss returns a HOLE (the open subgoal to abduce) | JIT-on-miss |
| `decompose <goal> <children> <mode>` | write a compound node; `compose(children) ⊨ goal` TESTED in simmer | write-once verdict |
| `put <node>` | idempotent insert, content-addressed dedup, returns the canonical node | idempotent |
| `merge <a> <b>` | union two DAGs | commutative, idempotent (meet law) |

Two holes, named not filled:
- `⊨` inside `plan`/`decompose` is the **matcher**: prose + judgment, optionally simmer-checked,
  propose-only (it never keys `put`'s dedup). Drafted as an exact normalized-string match until it
  visibly mispredicts.
- the node **record schema** past `status` is drafted minimal; the reliability fields
  (support/success/failure counts, abstraction version) are discovered on the first drive that
  JIT-misses, not authored now.

## Expressing uncertainty: a status and a trial, never a probability

Almost every node is a **guess** before it is tested — a freshly abduced decomposition, an
entailment the reasoner judged but hasn't run, a precondition it isn't sure holds. Prose
dagger expresses that uncertainty the Peircean way the rest of the system already runs on:
**not "how probable" but "how secured, and what experiment would secure it."** No float
credence (that would also break the idempotence law — see below). An uncertain element (a
pre/post, an entailment `⊨`, or a whole decomposition) carries three things:

1. **Conjecture-marked prose.** The text says it is a guess, not an assertion:
   `post: carried matches lock  (conjectured)`. The hedge is in the prose, visible to the
   reasoner reading the node.
2. **A security status, not a number** — `untested` (pure uberty) → `witnessed×N` (the *set*
   of trials it has survived) → `killed` (the trial that broke it, with a `from-kill`
   successor). This is arbor's `open / witnessed / killed` exactly; dagger stays structural
   and the status lives on the (eventually-arbor) claim the node points to. Credence accrues
   by **set-adding the trial that held it, never by `++`-ing a counter** — same constraint
   as the idempotence law (a witness keyed by trial-id is idempotent; a naive `credence++`
   double-counts a re-run and is the law going red).
3. **The discriminating trial and its cost class** — *how* you would settle it:
   `free` (run the children in simmer; reachability), `paid` (commit in piper; a state effect
   simmer is blind to, like the collected-token HUD), or `unmodellable` (no model yet). This
   is the `reachability-checkable` vs `state-checkable` split, generalized: the cost class
   tells the planner in advance whether resolving this uncertainty is free or spends budget.

**The forcing function:** an uncertainty you can't name a trial for is not a usable
hypothesis — drop it. Writing uncertainty *as the experiment that resolves it* filters
unfalsifiable guesses out of the DAG automatically. And the annotation **is** the node's
position on the uberty→security flow: untested nodes mark where to stay fertile, witnessed
nodes mark where to trust, so the planner reads its own confidence off the structure.

Worked (run3): `overlap-lock`'s precondition was
`carried matches lock — (conjectured); untested; trial: push and watch score — PAID`. The
driver paid the trial, it resolved false, that `killed` the token-less decomposition, and
`from-kill` reinstated `collect-token`. The uncertainty was legible, the trial was named with
its cost, and resolving it advanced the graph (a kill is progress, not a backstep).

Deferred (same ratchet): numeric credence, decay/staleness scores, any probability calculus.
We set-add trials and read status; a number earns its place only if prose status visibly
fails to discriminate two live options — and then it belongs in arbor, not here.

### Resolving uncertainty: surprise-driven, not champion/challenger A/B

The obvious way to resolve decomposition uncertainty is **champion/challenger**: hold a
best-guess decomposition, run challengers against it, compare, promote the winner. It works
but it is **expensive** — you pay to *evaluate challengers speculatively*, and under noise you
pay again for enough samples to be sure. Three things make it expensive, and this setting
removes all three:

1. **Nondeterminism forces statistics.** A/B needs many trials per arm to beat noise. The game
   is deterministic after RESET, so one counterexample is a *definitive* kill — `n=1`, no
   sampling, no significance.
2. **Expensive feedback forces real runs.** If evaluating a challenger means executing it,
   every comparison costs budget. simmer makes most comparisons **free**: any challenger whose
   discriminating trial is `reachability-checkable` is A/B'd at zero budget; only
   `state-checkable` differences touch piper. (This is what the cost-class annotation is *for*.)
3. **No simulator forces production A/B.** You A/B in the expensive environment only because
   there is nothing else to A/B in. simmer *is* that environment now.

So dagger keeps **one champion**, runs only it, and lets **surprise nominate the challenger**.
When the champion mispredicts (free to detect: `simmer ⊕ piper`, or simmer vs the corpus), that
specific failure *constructs* the successor via `from-kill`, and the successor is gated for free
against the **whole recorded corpus**. The challenger is never run speculatively — it is built
to **strictly dominate** (covers the counterexample plus everything the champion already
covered), so there is no A/B *decision*: the semilattice climb is monotone, and you paid only
for the champion's forward action, which advanced the game anyway. Uncertainty reduction is a
**byproduct of forward play**, not a separate budget line.

What survives of champion/challenger is the one case it earns its cost: two decompositions that
both commute in simmer but differ in a **state effect simmer cannot see**, where a long plan
depends on which is right. That is a single deliberate paid probe (PLAN's `decide()` "verify a
prediction a long plan depends on"), not a regime. The rule: **A/B freely in simmer, never
speculatively in piper.** Champion/challenger pays to evaluate guesses; surprise/from-kill pays
only to make progress and gets the challenger as a free byproduct of the champion's failure.

### The Boolean kill is a degenerate e-value test (and where e-values still earn their keep)

A principled champion/challenger hill-climb bets against the null "the champion is correct"
with an **e-value** (a test martingale): `E = p_challenger(observed) / p_champion(observed)`,
wealth growing only when you out-predict the champion, anytime-valid so you can stop the moment
`E` crosses `1/α`. Apply that to a **deterministic** champion — it predicts the next state with
probability 1 — and the moment it mispredicts one transition, `p_champion(observed) = 0`, so the
martingale jumps to **∞** at `n=1`. The threshold becomes irrelevant. So the layers split:

- **act-up / mechanics (deterministic, simmer-checkable):** the e-value process *collapses* to
  the Boolean kill. Anytime-validity is free — no betting, no threshold, no accumulation —
  because determinism makes one counterexample worth infinite wealth. e-value machinery here
  would be scaffolding around an `∞`. This is what the from-kill loop already is.
- **win-down / goal (sparse score, paid, plausibly stochastic / partially observed):** a
  surprising score-event is *not* infinite evidence (action→score is many-to-one and delayed,
  so the champion didn't assign it probability 0). There `E` accumulates gradually, and
  **optional stopping** is how you promote a goal-decomposition challenger on the *fewest paid
  piper actions*. This is the one layer where an e-value hill-climb genuinely earns its keep,
  and it is cheap there precisely because optional stopping spends the minimum.

A prior champion/challenger A/B is "rather expensive" when it runs e-value bets with no
simulator and no determinism — every bet is a paid real evaluation and you need many. Split by
layer the cost evaporates: free `∞`-wealth kills where deterministic, optional-stopping paid
bets only on the sparse goal layer. Two properties the surprise-driven climb gains over a
perturbation hill-climb: step size is `∞` in the deterministic layer (one definitive
counterexample, not wealth-to-threshold), and challengers are **counterexample-generated, not
perturbation-generated** (`from-kill` writes whatever covers the failure, structurally far from
the champion if need be), so it escapes the local-optimum trap.

Ratchet: build no e-value machinery now — the deterministic layer gives anytime-validity free.
Bank it as the correct tool for the goal layer the moment prose status cannot discriminate two
goal-decompositions under sparse score. Then it lives in arbor (the witness/credence ledger),
not here.

## The two roots meet at a commuting square

The same invariant covers both directions of the planner:

- **win-down** factors a goal morphism into subgoal morphisms (abduction; gated against the
  sparse score predicate).
- **act-up** composes action morphisms forward from the current state (deduction; free in
  simmer; gated against the dense transition corpus).

They **meet** when an act-up composite — a morphism from the start state — has a postcondition
that entails a win-down leaf subgoal. Two factorizations of the path-to-goal agreeing: the
plan *is* the proof the diagram commutes. Because act-up is free, expand it aggressively and
keep win-down shallow.

## JIT cache (unchanged from the post)

Resolution is recursive descent with four cases, and compilation = learning = **write**:

- **hit** — children populated → recurse, no LLM.
- **miss** — children absent → LLM decomposes once, writes children back, continue.
- **invalidate** — on failure overwrite the broken node; the parent factorization stays
  valid; re-resolve from the break.
- **learn** — a successful execution writes its resolution trace; a miss writes a
  decomposition speculatively, a success promotes it to trusted cache.

Indexed by intent (embedding nearest-neighbor over nodes), entered through multiple roots,
sub-actions shared across goals (one "route to X", referenced by every tree that needs it).

## Worked example (LS20, from the observed drive)

The per-level loop the subagent discovered is a sequence decomposition:

```
deposit-one-point            (goal; post: score += 1)
  = collect-token            (post: carried pattern toggled toward lock)
  ; route-to lock            (pre: token collected; post: avatar adjacent to lock)
  ; overlap-lock             (pre: carried matches lock; post: +1, level regenerates)
```

`route-to X` is the shared sub-action (a BFS over simmer's 5-cell lattice — the planner the
subagent had to improvise). Check the decomposition by running the three children in simmer
and asking whether `score` rose: if it did, the factorization commuted; if "carried matches
lock" was false at `overlap-lock`'s precondition, that *names* a missing child (a second
collect, or a route through a particular token) and `from-kill` inserts it. The win condition
is `deposit-one-point` repeated ×7 — the same node, seven hits.

## Resource admissibility = resource-constrained shortest-path DP (the live extension)

run4 broke the typing in the one place it had no slot: a decomposition can commute
geometrically (every child reachable in simmer) yet be **inexecutable** under a whole-sequence
resource budget (route length vs energy, with reset-on-depletion and 3 lives). The fix is a
route-node **admissibility witness** — resource-constrained shortest-path DP, NOT a numeric
planner and (per codex review) NOT a precomputed "optimal route" cache:

- search the **augmented state** `(position-projection × energy × lives × carried)`, cost =
  moves, edges from a witnessed `RouteModelClaim` (cost/move, refill cells, reset rule).
  There is ONE canonical state with NAMED PROJECTIONS — jotter's bar-masked hash is the
  *position projection* (one coordinate), NOT the state identity; the search key adds the
  resource coordinates plus model-revision and goal id. simmer stays pure geometry; the planner
  threads the resources; the driver refuses to pay piper for an inadmissible route; an
  infeasible decomposition is `from-kill`ed as resource-infeasible.
- it strengthens the invariant from geometric to **executable** entailment:
  `compose(children) ⊨ parent` now means *reaches the postcondition AND a route exists within
  budget under the current model*.
- routes are **conjectural until stepwise-verified**: before each paid action, predict the next
  step and compare to reality; on mismatch, kill the edge, invalidate dependents, replan. Only
  routes executed to goal are promoted to trusted dagger fragments. Minimum version is **lazy
  caching of executed successful suffixes**, not a full value table.

The sound residue of the certificate idea: a finite cost-certificate ≤ budget separates
deduce-for-free from must-refine-or-witness. `unmodellable` (above) = *no finite certificate
under the current abstraction*, escapable three ways — refine the abstraction, find a ranking,
or witness. (An earlier graded(-Elgot)-monad framing that tried to make `m* = ∞` itself *mean*
"must witness" was debunked in review and removed; see WORKLOG.)

## Deferred until it goes off the rails

Per the standing call: no formal machinery yet. Specifically deferred —
- a condition **DSL** or structural subsumption engine (prose + judgment until prose breaks);
- proving `compose(children) ⊨ g` (we test it in simmer instead);
- object-identity tracking across frames (simmer is grid→grid, needs no correspondence);
- minimality of a decomposition (the budget/RHAE pressure handles redundant children).

The trigger to harden any of these is the same ratchet everywhere: build it when the loose
version visibly mispredicts often enough that the wasted rollouts cost more than the machinery.
