# Module plan

Five module CLIs, in two groups: **two game interfaces** (real and simulated,
near-identical so they're swappable) and **three memory caches** (the three
cognitive stores). Every module obeys the **monoidal contract** so they compose
and test in isolation. Everything is CLI-accessible for independent testing — and
because the **driver is Claude Code itself** (it plays by calling these CLIs via
Bash on subscription tokens), CLI-accessibility is the whole interface, not just a
testing convenience.

## The driver is Claude Code (for now)

There is no driver module. **Claude Code is the single actor** running the serial
loop: it calls the module CLIs, reads their stdout, does the attend/abduce/decide
(the abductive band), and writes back via the cache CLIs. The five modules are its
instrument panel; the agent is the reasoner. This is the hygraph "division of
intellect": modules = harness (hold + gate, mechanical), Claude Code = reasoner
(attend + decide). Run `claude` in the project; it plays.

**Pluggable.** Claude Code drives *for now*; later a coded policy (or a different
agent) can drive the same CLIs unchanged. The CLI boundary is the decoupling seam,
so the driver swaps without touching the modules.

## Build as little as we can get away with

Principle: **develop the minimum for a working demo; let Claude Code do everything
it can in its own head.** The five-module architecture is the TARGET, not the demo.
For the demo Claude Code already covers most of it mentally:

| module | demo: who does it | codify into a module when… |
|---|---|---|
| **piper** (real game) | **MUST be code** — only way to reach the API | (already essential) |
| **simmer** (simulate) | Claude Code reasons "ACTION3 → block left 5" | it mispredicts often / needs systematic rollouts |
| **arbor** (hygraph) | Claude Code writes claims as prose (one md file) | the graph outgrows context / needs replay |
| **dagger** (plan) | Claude Code decomposes goals in reasoning | plans recur and re-deriving wastes budget |
| **jotter** (epmem) | Claude Code drives `git` directly via Bash | content-addressed dedup / transposition pays off |

So the **minimal demo = piper + a playbook + Claude Code.** We have ~90% of piper in
the current `arcg`. Every other module earns its existence only when Claude Code's
in-head version *visibly breaks* — which is cons/the ratchet applied to building the
system: do it manually, watch where it breaks, codify that part. Don't pre-build.

## The five modules

| module | etymology | role | group | paradigm |
|---|---|---|---|---|
| **piper** | pipe | the REAL game: I/O + perception (edge detection) | game interface | imperative (the inhale; costs budget) |
| **simmer** | sim / simmer | the SIMULATION: functional engine, near-identical interface to piper | game interface | functional (free; deduction) |
| **jotter** | notebook | epmem (multi-track): grounded facts + belief-provenance + action-provenance | memory cache | — |
| **arbor** | tree | smem: the hypothesis graph (claims, kill-edges, status, credence) | memory cache | declarative |
| **dagger** | DAG | pmem: the Action DAG (goal→action decompositions, JIT-on-miss) | memory cache | declarative+procedural |

### The two interfaces are swappable
piper and simmer expose an **identical operative interface** — the same verbs, same
args, same return shape (`reset / act / look / diff / state / score`) — so a call site
is byte-for-byte substitutable between them. The agent code is written once against
"a game" and pointed at either. **Interface identical, contract different**: that's
the whole point, and the distinction is load-bearing, not a fudge. The *operative
interface* (what you call and what comes back) is the same; the *contract* (cost,
exactness, mutation) is not — piper acts on reality (exact, budget-bearing,
side-effecting), simmer acts in imagination (free, approximate, pure). Substitutability
lives at the interface; the contract is what makes the swap *worth* doing. This is the
model-based core: **plan in simmer, commit in piper, reconcile by running both and
diffing** — only possible because the same code drives both. (So "identical semantics"
is the wrong test: identical *signature*, divergent *cost/exactness*. The reconcile
step exists precisely to measure the contract gap.)

### simmer is compiled from arbor
arbor holds the mechanic-claims (declarative); **simmer is their executable form** —
the witnessed claims composed into a pure functional `step`. `arbor → simmer` is the
compile (`arbor engine` folds the live, un-killed claims into `step`). When the agent
abduces a new claim into arbor, simmer recompiles. (Same knowledge, two paradigms:
declarative claims in arbor, functional engine in simmer — four-schools'
declarative↔functional pair.)

**The abductor IS the synthesizer; jotter's history IS the trial corpus.** A
mechanic-claim's `--trial` is "replay jotter's recorded transitions through the
candidate `step`"; `--kill-if` is "mispredicts any transition it claims to cover."
So gating is free and deductive against history — piper is touched only to *grow* the
corpus with novel transitions. Determinism licenses the Boolean gate: the game is a
pure function of its action sequence, so one counterexample is a *definitive* kill,
no thresholds, no statistics (exact regime). Granularity is per-object: a counter-
example kills only the rule for the object the diff touches; `from-kill` writes the
successor that covers it (gated against the *full* corpus, so it strictly dominates —
the rule set climbs the semilattice monotonically), and the kill-edge records which
transition broke it (jotter's belief-provenance, replayable).

**Overfitting is avoided BY the abductor, not by a held-out split.** A memorizing/
lookup rule is the maximally-overfit claim and dies first: the next novel `(s,a)` has
no entry → mispredict → `kill`. Witness credence accrues only on transitions the rule
hadn't seen (off-training-set by construction); `from-kill` forces generalizing
successors. The live loop's novel transitions are a continuous falsification feed. The
abductor gates and composes; it does **not** invent — the candidate rule body is the
agent's abductive leap from the red diff (reasoner attends+abduces, harness
holds+gates).

### jotter is multi-track provenance, not just a frame-log

jotter records the full trajectory, in tracks split by **integrity class**:
- **grounded facts** — observed states/deltas/scores. VERIFIABLE: deterministic,
  content-addressed, replayable. The skeleton the replay invariant holds on.
- **belief-provenance** — WHY each claim was believed (the surprise that triggered
  the abduction, the trial that witnessed it). Prose, TRUSTED not replayable; links
  to arbor's claims. (This is also the dependency cone collapse-and-rebuild needs.)
- **action-provenance** — WHY each action was taken. Reduce the commit message to a
  bare POINTER wherever a motivating node exists: `arbor:#<id>` (claim it tests) or
  `dagger:<id>` (node it executes). jotter then holds the provenance *edge*, not the
  rationale prose; arbor holds the content; `jotter why` dereferences. Sound because
  arbor is **write-once**: a node's identity+text never mutate in place (verdicts
  write-once, revisions are `from-kill` successors, witnesses append), so the pointer
  is a stable anchor with NO version-pinning — #4 later getting killed doesn't rewrite
  "I acted to test #4" (the kill is usually that action's own result). The one
  forbidden move: editing a claim in place. This upgrades action-provenance from
  trusted prose to a checkable edge (target exists? was it live at commit time?).
  Prose survives only at the pre-hypothesis frontier: undirected probes, and the first
  surprising actions that BIRTH a claim (they can't point forward to a node that
  doesn't exist yet — their prose is what abduction later reads). The action token is
  commit metadata, the tree is the fact.
  Because `message = ref(motive)` is a pure function of which node the decision
  selected, the *whole* commit is deterministic (tree from the action sequence, message
  from the motive), so jotter's content-addressed dedup holds: same `(state, action,
  motive)` → one node. This is the precondition for the idempotence law — a free-prose
  message would mint a phantom second node and break dedup. The non-determinism is
  quarantined to the *decision* (the reasoner's free choice of hypothesis); the
  *encoding* is mechanical, so the provenance is driver-agnostic (a coded policy that
  makes the same decision produces byte-identical commits). Push every motive to a
  content-addressed referent — `arbor:#<id>`, `dagger:<id>`, `surprise:<diff-hash>`,
  `explore:<state-hash>` — and the message is a typed edge with no prose at all.
  (Multi-motive actions need a deterministic selection rule — primary motive, or the
  full ordered ref-set — so the encoding stays single-valued.)

The line is the hygraph paper's: the mechanical skeleton (grounded facts) is
checkable; the prose (the two rationale tracks) is what an auditor would otherwise
have to trust. Recording the *why* is the reasoning agents normally discard, and
what cons's *attend* consolidates. git carries all three for free: commit **tree** =
grounded fact, commit **message** = action rationale, git **notes** = belief
rationale (attached without changing the content hash). The two rationale tracks
both touch arbor but in opposite directions: a commit **message** refs a claim to
say *this action tests it* (motivation, forward); a git **note** refs the same claim
to say *it is believed because of evidence E* (justification, backward). Same node,
opposite provenance direction — so `jotter why` can walk either way.
CLI sketch: `jotter commit --action <a> --why "<reason>" [--for arbor:#<id>|dagger:<id>]`,
`jotter believe <claim-id> --because "<reason>"`, `jotter log --track
facts|beliefs|actions`, `jotter why <state-hash|claim-id>`.

### Where consolidation lives
There is no separate consolidator module: the **driver + the agent (LLM)** do it,
left blank/agent-driven by design (see WORKLOG). They use jotter's `diff` to compute
the surprise (piper ⊕ simmer) and arbor's CRUD to write claims. The cache laws make
a loose consolidate converge anyway.

### goals and actions meet in the middle (dagger)
dagger is **two roots growing toward each other**, the two inference directions:
- **'win' top-down = abduction** — regress the goal predicate into subgoal
  predicates (a guess; needs the prior; gated against jotter's *score* track,
  sparse). Grows the frontier of *what I need to make true*. Predicate space.
- **'act' bottom-up = deduction** — push actions forward through arbor's mechanics
  into reachable states (free in simmer; gated against the *transition* track,
  dense). Grows the frontier of *what I can make true*. State space.

The **plan is where the frontiers meet**: a reachable state satisfies a leaf
subgoal, discharging a hypothesized subgoal into a verified path (bidirectional /
means-ends search). Because deduction is free, expand act-up aggressively and keep
win-down shallow. arbor is the **shared alphabet** both roots are spelled in (every
act-step uses a witnessed mechanic; every win-entailment is checked through the
mechanics), not a third root. Both stay JIT: act-up expands from the current state,
win-down decomposes only on miss.

A **failure to meet routes the agent** (the planning gap is a diagnostic, not a dead
end): nothing reachable satisfies a subgoal → re-abduce the goal; subgoals
unreachable → spend piper to learn the missing mechanic; children achieved but parent
won't fire → `from-kill` a better decomposition. Goal predicates compose with the
monoidal algebra already in the contract: conjunction (commutative idempotent =
meet-semilattice = the merge law), sequence (non-commutative = the action monoid).
(Peirce closes: abduce = win-down, deduce = act-up, induce = arbor's witness.)

## The monoidal contract (every module)

- **identity** — a null/empty element + null op (empty jotter/arbor/dagger;
  `reset` is the interfaces' identity). Applying it changes nothing.
- **associativity** — grouping of composed ops doesn't change the result
  (`act∘act`, cache merges).
- **idempotence** — the test is `f ≠ I ∧ f∘f = f`: a *non-trivial* idempotent. On an
  already-converged state `f = I` and the law says nothing (that vacuous case is the
  "fake rigor" smell); the fixture must start where the op BITES — apply once, assert
  the state changed (`f ≠ I`); apply again, assert it didn't (`f∘f = f`). Witnesses:
  `jotter commit X` (set-add, then dedup), `arbor kill #n` (write-once), cache
  `merge b` for `b ⊄ state` (semilattice join). The clause *delimits* the law as much
  as it asserts it: `piper act` FAILS it by design (act twice moves twice, spends
  twice), so act is never claimed idempotent — the test is the discriminator between
  cache writes and the budget-bearing game op. It also forces the discipline: a write
  passes only if keyed by content/evidence (a join); a naive `arbor witness` doing
  credence `++` goes red until it's keyed by trial-id (set-add the evidence — the law
  and the correct "don't double-count a trial" semantics are the same constraint).
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

## CLI conventions (all five modules — model: abductor/src/abductor/cli.py)

Agent-first (clig.dev baseline, bent toward an agent in a debug loop, not a human at
a prompt). Two rules carry the surface:

1. **The tool never judges.** Every command is a deterministic op over a cache —
   act, diff, reconcile, abduce-append, replay. No command proposes, ranks, or
   decides what a result means; that is the driver's (Claude Code's) job. No
   `diagnose`, no `suggest`. (This is "modules = harness, Claude Code = reasoner.")
2. **The exit code is the verdict.** The driver routes on the status code without
   parsing stdout. Publish an `EXIT_CODES` table and a `<tool> codes` command so the
   driver never scrapes docs. Convention: `0` ok/agree, `10` disagree/surprise,
   `2` usage, `3` not-found, `4` undecoded; reserve others per module.

Output contract: artifact → **stdout as JSON** (default when stdout isn't a TTY;
`--human` forces a table, `--pretty` expands); narration + errors → **stderr**;
**no command ever prompts**. `-` means stdin. State lives in a file located by an
env var (e.g. `PIPER_SESSION`, `ARBOR_GRAPH`).

**Instructive error messages** (the key convention). Every error names *what went
wrong AND what to do*, tool-prefixed, on stderr. Encode the invariants in the error
text so the driver learns the rules by hitting them:
- `piper: no active game; run \`piper start <game>\` first`
- `piper: ACTION6 needs --x and --y in 0-63; got x=70`
- `piper: budget cap 15 reached (15 spent); run is over — \`piper end\` to close`
- `jotter: no state {hash}; never visited — act to reach it`
- `arbor: #4 is already killed; verdicts are write-once — succeed it with \`arbor from-kill 4 "<next>"\``  (encodes the write-once axiom)
- `arbor: can't link to #3: it is open, a successor links only to a killed node`

**Design-by-contract** (every module; four-schools' Imperative+Declarative seam =
Hoare logic / Eiffel DbC). Each command carries a three-part contract:
- **interface + preconditions = TYPES + ASSERTS.** Typed signatures are the
  interface; `assert`s at entry enforce preconditions and fail loud with a
  tool-prefixed instructive message (a precondition violation IS an instructive
  error): `assert 0 <= x <= 63, f"piper: ACTION6 x must be 0-63, got {x}"`. The
  driver learns preconditions by hitting them.
- **postconditions = COMMENTS in `--help`.** What the command guarantees on success,
  in the progressive reference: `piper act --help` → "Post: budget += 1; new frame
  committed to jotter; returns the deterministic successor."
- **invariants = the monoidal / cache laws, asserted.** `arbor witness` asserts the
  node was `open` (write-once); `jotter commit` asserts content-addressed dedup.
  The laws that make a loose consolidate converge, machine-checked not just documented.

**Onboarding by progressive disclosure** (per the explainer decision): each tool
embeds a short **driving-contract** string (the loop, printed on no-args / `<tool>
help`) = the explainer/map; `<tool> --help` = role + subcommands + key principle;
`<tool> <cmd> --help` = specifics. The session explainer points here; detail is
pulled on need. Magnitude-honest previews (always show the count, never let a capped
list read as the whole set).

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

## Build order (minimal demo first, then codify on observed need)

**Milestone 0 — the demo (build only this):**
1. **piper** — refine the existing `arcg` into the piper CLI: ensure
   act/look/diff/snapshot/restore + add `undo` (ACTION7) and `objects` (spatial
   edges). The one essential build (~90% exists). Live-testable on LS20.
2. **explainer prompt** — a short session-onboarding prompt that catches the driver
   up: the goal, the serial loop (perceive → predict in-head → act / experiment via
   snapshot/restore/undo → reconcile in-head → note claims as prose → plan in-head →
   repeat), *which tool for which job*, and the principles (determinism → cheap
   exact experiments; budget → spend only on novel ∩ surprising, reason for free;
   figure/ground → the delta localizes what an action did). A MAP, not a manual —
   it names tools and defers the how to `--help`.
3. Run `claude` on LS20 with the explainer. That's the working demo. Everything
   else is in Claude Code's head + prose notes + git via Bash.

### Onboarding the driver: explainer + progressive disclosure

Two layers, lazy-loaded so the driving session's context stays lean:
- **explainer prompt** = the map (loop, tool→role, principles). Short. In the
  session. Says *what to use when*, not *how*.
- **`--help` = the reference**, progressively disclosed: `piper --help` → role +
  subcommand one-liners + key principle; `piper act --help` → specifics (actions,
  coords, return shape, budget cost). The driver pulls detail only when it reaches
  for a tool. Each module's `--help` is written as onboarding, not just flags.
Context flows explainer → `tool --help` → `tool subcmd --help`, each loaded on need.
Budget-conscious by construction: no preloading every tool's API.

**Then, only when the in-head version visibly breaks (the ratchet):**
4. **jotter** — when content-addressed dedup / transposition pays off (lots of
   reconvergence, or context can't hold the history).
5. **arbor** — when the hypothesis graph outgrows context or needs replay; port the
   abductor `hygraph.py`.
6. **simmer** — when in-head simulation mispredicts often or needs systematic
   rollouts; functional engine compiled from arbor, piper's interface.
7. **dagger** — when plans recur and re-deriving them wastes budget; Action DAG.

Each codified module is testable alone and obeys the monoidal contract; each is
introduced because Claude Code's manual version was observed to break, not on spec.

## Open

- **driver name** — the orchestrator is the one unnamed piece. Candidates: `loom`
  (weaves the threads), `arc`, `play`. TBD.
