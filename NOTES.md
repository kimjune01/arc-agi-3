# Research log — arc-agi-3

## The problem
ARC-AGI-3 = interactive reasoning. Not static input→output grids; small *games*.
Agent sees a grid `frame`, picks an action, gets the next frame, repeats until
`WIN` or `GAME_OVER`. Rules are never given — learned by acting.

## API ground truth (OpenAPI 1.0.0, https://docs.arcprize.org/arc3v1.yaml)
- Base `https://three.arcprize.org`, auth header `X-API-Key` (free console key).
- `GET /api/games` → `[{game_id, title}]`.
- `POST /api/scorecard/open` → `{card_id}`; `/close` finalizes & returns score.
- `POST /api/cmd/RESET` `{game_id, card_id, guid?}` → first frame. Omit `guid`
  for a new session; two consecutive RESETs = fully fresh game.
- `POST /api/cmd/ACTION1..5,7` `{game_id, guid, reasoning?}` (reasoning ≤16KB).
- `POST /api/cmd/ACTION6` adds `{x, y}`, each 0-63 (the "complex"/click action).
- Frame: `{game_id, guid, state, frame, levels_completed, win_levels,
  available_actions}`. `available_actions` are **ints** (e.g. [1,2,3,4]).
  `state ∈ {NOT_PLAYED, NOT_FINISHED, WIN, GAME_OVER}`. Score = `levels_completed`.
- **Session affinity**: responses set `AWSALB*` cookies that must ride on every
  later request. One `httpx.Client` per session handles this.

## Status
- Harness built: `client.py` (HTTP) + `agents/base.py` (loop+verdict) +
  `agents/random_agent.py` (baseline) + `main.py` CLI.
- Loop logic verified offline (tests/test_loop.py) — random agent yields e.g.
  `[FAIL] ls20-demo  state=GAME_OVER  score=0/10  actions=7`. The failing floor.
- **Blocked on live run**: need `ARC_API_KEY` in `.env` to hit the dev games.

## Subscription tokens
The LLM-driven agent (later) should reason via the Claude *subscription*, not
metered API billing. Doesn't affect the random baseline (no LLM).

## Perception loop (built)
`perception.py` — stateful `Perception.observe(frame) -> Observation`:
- `render_grid`: 64x64, one hex char/cell, '.'=empty. Lossless, ~4KB/frame.
- `diff_grids`: delta vs previous frame = (changed count, cell list, bbox). The
  key learning signal — localises what an action moved.
- `Observation.to_prompt()`: colour histogram + available actions + delta +
  optional grid, ready to hand to an LLM policy.
- Wired into `base.Agent.play` (per-step `observe`, `on_observe` callback).
  `arc3 --render` streams it live.

### LS20 read (from live deltas)
64x64. Left column is a `5` UI bar; `4` is background; `3` are corridors.
A **`12`-coloured ~5-wide block** in rows 40-62 slides one step per action
(`12<->3` swaps trace it). Strong candidate for the avatar. ACTION1-4 available
(directional). Win = 7 levels. Next: confirm which action = which direction,
and what the `9`/`c`/`1` tokens are (goal? keys?).

## Policy loop (built) — Claude via subscription
`policy_claude.py` shells out to `claude -p ... --output-format json` (subscription
auth, no API key) and reads `result`. `agents/llm_agent.py` (`LLMAgent`):
- Per step: feed `Observation.to_prompt()` (grid + delta + palette + actions)
  plus a rolling scratchpad of Claude's own `note`s (last 8).
- Claude returns one line of JSON `{action, x, y, note}`; robust parser with
  fallback to a random available action on any malformed/unavailable output.
- Run: `arc3 --agent claude --game ls20 --max-actions N --model sonnet`.
- Cost/latency: one CLI call per step (~5-15s). Keep max-actions low while
  iterating. Grid is ~4KB/step; consider delta-only prompts later.

## Agent tools (built) — `arcg`
Stateful CLI (`tools.py` + `session.py`) so a shell-using agent plays by calling
commands: `games/start/look/act/note/status/reset/end`. Session persists in
`.arc/session.json`. `AGENT.md` is the playbook.
- **Gotcha fixed**: the API sets multiple `GAMESESSION` cookies; httpx
  `cookies.items()` raises `CookieConflict`. Must iterate `cookies.jar` and keep
  domain/path. These cookies are the cross-process session affinity — without
  persisting them, `act` in a new process loses the session.
- Verified live: ACTION3 slides the 12-block left ~5 cols; ACTION1 cleared an
  `11` token at the grid bottom (row 61-62, col 14) — possibly a move counter.

## Rules (verified vs docs 2026-06-24 — trail in WORKLOG.md)
- Actions: ACTION1=up, 2=down, 3=left, 4=right, 5=interact/select/rotate,
  6=complex(x,y 0-63), **7=undo**, plus RESET. (ACTION3=left matches our live
  observation of the 12-block.)
- Scoring = RHAE efficiency: `(human_baseline_actions / ai_actions)^2`, cap 1.15x.
  Every state-changing action lowers score; only non-state-changing reasoning is
  free. "Replay counts against budget" holds — as a continuous efficiency penalty.
- **Determinism is NOT documented** — only implied by replayable runs. Treat as a
  hypothesis to measure (that's what Layer 2's restore-check does), not a given.
- ACTION7=undo means cheap O(1) single-step backtrack exists; reset+replay (O(N))
  is only for arbitrary jumps.

## Open questions
- Which dev games are exposed, and their action semantics per title?
- Exploration strategy: the 3rd-place preview solution was "explore till you
  solve it" (https://github.com/dolphin-in-a-coma/arc-agi-3-just-explore) —
  worth reading before designing the real agent.
- How to feed frames to an LLM cheaply (grid → compact text? deltas only?).
