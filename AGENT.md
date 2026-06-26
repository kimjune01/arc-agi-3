# Playing ARC-AGI-3 with the `arcg` tools

You are playing an unknown 64x64 grid puzzle game. You are not told the rules —
learn them by acting and watching what changes. Drive the game entirely through
`arcg` commands (one session persists in `.arc/session.json`). You think in game
terms (Layer 1+); you never need ACTION-numbers or session ids.

## Commands

Perception & intent (Layer 1):
| command | what it does |
| --- | --- |
| `uv run arcg look` | render the current board (grid + colours + last delta) |
| `uv run arcg move up\|down\|left\|right` | move; prints the resulting delta + frame |
| `uv run arcg interact` | ACTION5 (select/rotate/use) |
| `uv run arcg click <x> <y>` | act at a coordinate, 0-63 (ACTION6) |
| `uv run arcg undo` | undo the last action (ACTION7) |
| `uv run arcg diff` | the delta since your last action |
| `uv run arcg objects` | connected-component objects by colour; meaning is game-specific (controls, targets, walls, ...); FREE |

**Which verbs apply depends on the game.** `look`/`start` report the *available actions* — a game may offer only `click`, or only moves. Check that list; don't assume navigation.

State & determinism (Layer 2) — the game is deterministic after RESET:
| command | what it does |
| --- | --- |
| `uv run arcg history` | your action sequence, budget spent, snapshots |
| `uv run arcg snapshot <label>` | name the current state (= the action sequence) |
| `uv run arcg peek <label>` | view a snapshot's state from cache — FREE, no budget |
| `uv run arcg restore <label>` | go back to a snapshot (RESET + replay) — COSTS budget |

Memory (Layer 3): `uv run arcg note "<finding>"` · `uv run arcg notes`
Lifecycle (Layer 0): `uv run arcg start <game> [--budget N]` · `uv run arcg end`
Escape hatch: `uv run arcg act ACTION1..7 [--x --y]` if the move-mapping doesn't fit.

## How to read a frame
- Grid: one hex char per cell, `.` = empty. Values 0-15 are colours.
- `since last action: N cells changed ...` is your key signal — it localises the *effect* of
  your action (which may be local, remote, or on a status meter) and shows what the action did.
  An action that changes nothing acted on an inert region — not necessarily a wall.

## Budget — every action counts
Scoring is efficiency (RHAE): fewer actions = higher score. The budget meter
(`actions spent X/cap`) is real. `restore` is expensive — it replays the whole
sequence, each step costing budget. `peek` is free; prefer it for thinking.
`undo` is one cheap step back. When the cap is hit, the tools terminate.
Some games also render the step budget on the board as a thin depleting strip (any colour, any
edge — it loses one cell per action); read it as a move counter, not as energy/health.

## Loop
1. `start <game>`, then `look` + `objects`. Read the available actions — they set the game type.
2. **Discover the controls**: probe one cell of each salient region, diff. A change = a control
   (note *where* its effect landed); no change = inert region, not a wall.
3. **Name the win-model** (path / configuration-match / selection / sequence), then test toward
   it: predict an effect, act once, read the delta; `note` what you learn (e.g. "region R
   toggles", "click on a tile flips it", "top strip is a step counter").
4. `snapshot` before a risky branch; `restore` (or `undo`) if it goes wrong.
5. Drive `score` to the target (`score X/N` is often N independent sub-conditions, not a path).
   Stop at WIN/GAME_OVER, then `end`.

Be economical: once you know what an action does, don't re-test it. Think, then
issue exactly one action.
