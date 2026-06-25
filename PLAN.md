# Module plan

Five modules + a driver, in two groups: **two game interfaces** (real and
simulated, near-identical so they're swappable) and **three memory caches** (the
three cognitive stores). Every module obeys the **monoidal contract** so they
compose and test in isolation. Everything is CLI-accessible for independent
testing and debugging.

## The five modules

| module | etymology | role | group | paradigm |
|---|---|---|---|---|
| **piper** | pipe | the REAL game: I/O + perception (edge detection) | game interface | imperative (the inhale; costs budget) |
| **simmer** | sim / simmer | the SIMULATION: functional engine, near-identical interface to piper | game interface | functional (free; deduction) |
| **jotter** | notebook | epmem: a git repo (states, patches, transposition, branches) | memory cache | — |
| **arbor** | tree | smem: the hypothesis graph (claims, kill-edges, status, credence) | memory cache | declarative |
| **dagger** | DAG | pmem: the Action DAG (goal→action decompositions, JIT-on-miss) | memory cache | declarative+procedural |

### The two interfaces are swappable
piper and simmer expose the **same game API** (`reset / act / look / diff / state /
score`). The agent code is written once against "a game"; point it at piper to act
on reality (exact, budget-bearing) or simmer to act in imagination (free,
approximate). This is the model-based core: **plan in simmer, commit in piper,
reconcile by running both and diffing.**

### simmer is compiled from arbor
arbor holds the mechanic-claims (declarative); **simmer is their executable form** —
the witnessed claims composed into a pure functional `step`. `arbor → simmer` is the
compile. When the agent abduces a new claim into arbor, simmer recompiles. (Same
knowledge, two paradigms: declarative claims in arbor, functional engine in simmer —
four-schools' declarative↔functional pair.)

### Where consolidation lives
There is no separate consolidator module: the **driver + the agent (LLM)** do it,
left blank/agent-driven by design (see WORKLOG). They use jotter's `diff` to compute
the surprise (piper ⊕ simmer) and arbor's CRUD to write claims. The cache laws make
a loose consolidate converge anyway.

## The monoidal contract (every module)

- **identity** — a null/empty element + null op (empty jotter/arbor/dagger;
  `reset` is the interfaces' identity). Applying it changes nothing.
- **associativity** — grouping of composed ops doesn't change the result
  (`act∘act`, cache merges).
- **idempotence** — re-applying on a converged state is a no-op (two-pass
  convergence; dedup). `jotter commit X; jotter commit X` → one node. Deterministic
  replay on both interfaces is idempotent by construction.
- **commutative merge** (caches) — `merge(a,b)=merge(b,a)`, a join-semilattice /
  CRDT. Axiom: write-once centers, fire-on-presence, collapse-and-rebuild on rot.
  This is what lets the loose/agent consolidate still converge.

So the whole pipeline is monoidal — composable and convergent by construction.

## Dependency order (downward only, triangular reach)

```
piper        (real game: I/O + perception)     ← imports the API client only
  jotter     (git epmem)                         ← records piper's frames
    arbor    (hygraph smem)                       ← claims about the episodes
      simmer (functional sim, piper's interface)  ← compiled from arbor
        dagger (action-dag pmem)                  ← plans via simmer rollouts
          driver (the synchronous loop)           ← reconciles piper⊕simmer, drives consolidation
```
A test (`tests/test_layering.py`, ported) derives this from a manifest and forbids
upward imports. Only piper imports the game client.

## CLI surfaces (each independently runnable)

```
# game interfaces — SAME shape, real vs simulated:
piper  reset | act <ACTION> [--x --y] | undo | look [--no-grid] | diff | objects | games | start | end
simmer reset | act <ACTION> [--x --y] | look [--no-grid] | diff | compile   # compile = rebuild engine from arbor

# memory caches:
jotter commit --action <a> | log | show <hash> | diff <a> <b> | has <state-hash> | branch | checkout | merge <a> <b>
arbor  abduce <claim> --trial <cmd> --kill-if <c> | witness <id> | kill <id> | from-kill <id> <claim>
arbor  probe <claim> <cand> | query [--open] | engine | merge <a> <b>
dagger plan <goal> | decompose <goal> | skills | put <skill> | merge <a> <b>

# driver:
driver play <game> [--budget N]
```
Each module's `merge`/identity is exposed so the monoidal laws are testable from the
CLI (run twice → same; merge two → order-independent). And piper/simmer being
identical-interface means you can A/B them by hand: `piper act X` vs `simmer act X`.

## The serial loop (driver)

Synchronous, no actors, no queues:

```
per step:
  s      = piper.look                          # perceive (edge detection)
  pred   = simmer.act(a)                        # deduction, free (sim = compiled arbor)
  real   = piper.act(a)                         # the imperative inhale — only on novel ∩ surprising
  jotter.commit(real, a)                        # record (content-addressed; dedup; never re-query a state)
  surprise = jotter.diff(pred, real)            # XOR: piper ⊕ simmer
  if surprise: agent abduces → arbor.*          #   → arbor recompiles simmer (consolidate, agent-driven)
  else:        arbor.witness(...)               #   credence up, no new node
  plan   = dagger.plan(goal)                    # decompose toward the goal, over simmer rollouts
  a'     = decide(plan, surprise, budget)       # spend real budget only where simmer is unsure
```
Most exploration runs on simmer (free); piper is touched only for the irreducible
`novel ∩ surprising` transitions.

## Mapping to existing code

- **piper** ← `client.py` + `perception.py` + games/start/act/look/diff/end from the
  current `arcg`.
- **jotter** ← NEW git module; absorbs the determinism cache, adds content-addressing
  + branches + merge.
- **arbor** ← NEW; port the abductor `hygraph.py` (abduce/kill/witness/from-kill/
  probe) as the smem interface.
- **simmer** ← NEW; the functional engine compiled from arbor + the same game API as
  piper. Reconcile/IBLT (`iblt.py` port) lives at the driver seam (piper⊕simmer).
- **dagger** ← NEW; Action DAG (HTN cache + JIT-on-miss).
- **driver** ← NEW thin orchestrator (the synchronous loop). [name TBD]

## Build order (each shippable + testable alone)

1. **piper** — mostly exists; repackage + CLI + idempotent perceive. Live on LS20.
2. **jotter** — git substrate + transposition + branches + merge. Offline (dedup, idempotence, merge order-independence).
3. **arbor** — port hygraph; CRUD + merge. Offline (idempotent claims, order-independent merge).
4. **simmer** — functional engine compiled from arbor, piper's interface; A/B against piper on logged sequences.
5. **dagger** — Action DAG + plan/decompose over simmer. Offline then live.
6. **driver** — wire the synchronous loop; reconcile piper⊕simmer; live on LS20, tight budget.

## Open

- **driver name** — the orchestrator is the one unnamed piece. Candidates: `loom`
  (weaves the threads), `arc`, `play`. TBD.
