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

### Built so far (before this planning round)
- REST client (OpenAPI-faithful), perception (grid render + frame delta),
  random baseline, programmatic Claude policy (`arc3`), agent-facing `arcg`
  tools (`games/start/look/act/note/status/reset/end`), session persistence with
  AWSALB cookie carryover (bug fixed: httpx CookieConflict on duplicate
  GAMESESSION → iterate the jar). 14 offline tests pass.
- Live: random agent scores 0; Claude policy drives real actions via
  subscription; `arcg` plays LS20 end-to-end.
