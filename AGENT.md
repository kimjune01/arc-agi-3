# Playing ARC-AGI-3 with the `arcg` tools

You are playing an unknown 64x64 grid puzzle game. You are not told the rules —
learn them by acting and watching what changes. Drive the game entirely through
these shell commands (one game session is persisted in `.arc/session.json`):

| command | what it does |
| --- | --- |
| `uv run arcg games` | list available game ids |
| `uv run arcg start <game>` | open a scorecard, reset, print the first frame |
| `uv run arcg look` | re-print the current observation (grid + palette + actions) |
| `uv run arcg act ACTION1` | take a simple action; prints the DELTA + new frame |
| `uv run arcg act ACTION6 --x 12 --y 34` | the complex (click/place) action, coords 0-63 |
| `uv run arcg note "<memory>"` | jot a finding into the scratchpad |
| `uv run arcg status` | compact state/score/step + your notes |
| `uv run arcg reset [--full]` | reset the current level (or whole game) |
| `uv run arcg end` | close the scorecard, clear the session |

## How to read a frame
- Grid: one hex char per cell, `.` = empty (value 0). Values 0-15 are colours.
- `available actions` tells you which of ACTION1-7 are legal this turn.
- `since last action: N cells changed ...` is your key signal. It localises your
  avatar and reveals what each action does. A move that changes nothing hit a
  wall or did nothing — try a different one.

## Loop to run
1. `uv run arcg start <game>`, read the first frame.
2. Form a hypothesis about which action does what; `uv run arcg act` to test it.
3. After each act, read the delta. `uv run arcg note` anything you want to remember
   (e.g. "12-block = avatar", "ACTION3 = move left 5 cols", "11-token at bottom
   is a move counter").
4. Drive `score` (levels_completed) up toward the win target. Stop at WIN or
   GAME_OVER, then `uv run arcg end`.

Be economical: once you know what an action does, don't re-test it. Think before
each act; explain your reasoning briefly, then issue exactly one `uv run arcg act`.
