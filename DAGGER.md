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

## Deferred until it goes off the rails

Per the standing call: no formal machinery yet. Specifically deferred —
- a condition **DSL** or structural subsumption engine (prose + judgment until prose breaks);
- proving `compose(children) ⊨ g` (we test it in simmer instead);
- object-identity tracking across frames (simmer is grid→grid, needs no correspondence);
- minimality of a decomposition (the budget/RHAE pressure handles redundant children).

The trigger to harden any of these is the same ratchet everywhere: build it when the loose
version visibly mispredicts often enough that the wasted rollouts cost more than the machinery.
