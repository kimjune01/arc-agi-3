# Grades: the resource gate is a graded(-Elgot) monad

Theory note for DAGGER.md's resource-admissibility witness. Why the energy gate is a *grade*
(not an LP constraint), why the iteration stays decidable, and why `unmodellable` is a real
cost-class. Sources: the `graded_elgot_in_python.py` draft, `reading/natural-breadcrumbs/*`
(Fritz-Perrone on Markov categories, Aguirre-Katsumata), `reading/the-natural-framework-lean/
hoare-graded`.

## The grade is energy

`E = (ℕ ∪ {∞}, +, 0, ≤)`, the cost monoid from `graded_elgot_in_python.py`. A computation
graded by `m` uses `m` energy; each move costs a fixed grade; a route's grade is the sum. So
we have a **graded monad**: `T_m` = reachability-at-cost-`m`, unit `η : Id → T_0` (a value
costs nothing), multiplication `μ : T_m T_n → T_{m+n}` (grades compose along a route). The
underlying monad is nondeterministic reachability, the reconverging lattice (powerset /
join-semilattice). The object is a **cost-graded nondeterministic reachability monad**.

## A* = least-grade Kleisli search

A* searches the Kleisli category of this graded monad for a minimal-grade morphism
`start → goal`: `g` = accumulated grade, `h` = a lower bound on the remaining grade (lattice
distance), the optimum = the least-grade path, admissible iff that grade ≤ budget. So the
"sum of step costs ≤ budget" that smelled like LP is just graded `μ` plus a cap: grades
**compose** (a monoid action), they are not constraints to **solve**. That is the whole reason
the smell was a false alarm.

## Reset = graded Elgot, bounded into Layer 2

The energy reset is the Elgot dagger `f : X → T(Y + X)`, with `Y` = reached-goal-exit and
`X` = depleted-reset-continue (`graded_elgot_in_python.py` Layer 2). The draft's Layer-3 gap:
an *unbounded* additive loop has no finite static grade (`star_additive(m) = ∞` for `m > 0`;
Gordon's laxly-iterable closure `m*` is unpublished as a coherent graded dagger — GMR's dagger
discards its parameter at the unit, Orchard-Wadler-Eades show graded ≠ parametrized).

We never reach the gap. The loop is **bounded by a well-founded fuel**: lives (≤3) cap the
iteration count, energy (~21) caps each leg. So `k` is static and the grade is the plain
Layer-2 product of bounds, finite and computable by A*. The "terminal-at-traversal-length,
finite search space" property *is* the fuel bound that keeps us in Layer 2. We never need the
unpublished closure.

## The Layer-2 / Layer-3 line is the deduction / induction (free / paid) line

The payoff. The boundary between **Layer 2** (bounded loop, finite static grade) and
**Layer 3** (unbounded loop, `m* = ∞`) is the agent's **deduction / induction** boundary:

- a bounded resource question has a finite static grade → **free A* (deduction, simmer)**;
- an unbounded loop (a game that lets you farm a resource indefinitely) has static grade `∞`:
  you cannot deduce the cost, you must run it and **witness it (paid induction, piper)**.

So the graded-Elgot gap is the **categorical signature of the `unmodellable` cost-class** in
DAGGER.md's uncertainty section. `unmodellable` = `m* = ∞`: a trial whose grade is statically
undefined, resolvable only by spending budget. free/deduction/Layer-2 vs paid/induction/
Layer-3. That is the cleanest justification that `unmodellable` is a real third class and not a
hedge — it is exactly the loops whose static grade cannot close.

## Typing home: graded Hoare

The route node is a graded Hoare triple `{start, carried} route {goal, score+1} @ grade`,
admissible iff `grade ≤ budget` (`hoare-graded`; `natural-breadcrumbs/aguirre-katsumata-2022`).
Sequencing multiplies grades (the monoid); nothing is optimized. This is codex's resource gate
made principled: the resource is a *grade on the triple*, not a numeric fluent, so it cannot
infect the loose prose system with a stealth LP / PDDL planner.

## Soundness of the lattice collapse: Markov

Collapsing the reconverging lattice (two input sequences → one config; jotter's canonical hash)
is sound because configuration is a deterministic state — the future is path-independent
(Markov). That is the copy/discard structure Fritz-Perrone formalize
(`natural-breadcrumbs/fritz-perrone-2021`). So **lattice**, **graded**, and **content-addressed
dedup** are three views of one object: a cost-graded deterministic (Markov) reachability monad,
searched by A* with the canonical hash as node identity.

## What this licenses building (and what it does not)

Licenses (DAGGER.md): admissibility as A* over `(cell, energy, lives, carried)`, grade =
energy, node identity = jotter's canonical hash, simmer stays pure geometry, the `EnergyClaim`
is the witnessed grading.

Does **not** license: the unpublished graded dagger, a general numeric / PDDL planner, or
statically grading an unbounded loop. A game that presents an unbounded resource loop is
Layer 3 / `unmodellable` — witness it, do not deduce it.
