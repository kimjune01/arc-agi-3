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
