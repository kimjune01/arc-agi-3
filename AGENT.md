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
- `since last action: N cells changed ...` is your key signal — it localises your
  avatar and shows what an action does. A move that changes nothing hit a wall.

## Budget — every action counts
Scoring is efficiency (RHAE): fewer actions = higher score. The budget meter
(`actions spent X/cap`) is real. `restore` is expensive — it replays the whole
sequence, each step costing budget. `peek` is free; prefer it for thinking.
`undo` is one cheap step back. When the cap is hit, the tools terminate.

## Loop
1. `start <game>`, then `look`.
2. Hypothesise what an action does; test it with one `move`/`interact`/`click`.
3. Read the delta; `note` what you learn ("12-block=avatar", "ACTION3=left").
4. `snapshot` before a risky branch; `restore` (or `undo`) if it goes wrong.
5. Drive `score` toward the win target. Stop at WIN/GAME_OVER, then `end`.

Be economical: once you know what an action does, don't re-test it. Think, then
issue exactly one action.
