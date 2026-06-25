# arc-agi-3

Research toward an agent that plays the **ARC-AGI-3** interactive reasoning
benchmark — small games where the agent learns the rules by acting, aiming to
reach a `WIN` state. Research log and API ground truth: [`NOTES.md`](./NOTES.md).

## Setup

```bash
uv sync
cp .env.example .env      # then paste your free key from three.arcprize.org
```

## Play (default: agentic)

The default agent is Claude driving the game itself through a stateful CLI.
Point it at the playbook and let it go:

```bash
claude "Read AGENT.md, then play ls20 with the arcg tools until WIN or GAME_OVER."
```

It plays by calling these `arcg` commands and reading their stdout; the session
(ids, grid, affinity cookies, notes) persists in `.arc/session.json` between
calls, so each command continues the same game:

```bash
uv run arcg start ls20 --budget 15  # open, reset; tight cap for test runs
uv run arcg look                    # render the board
uv run arcg move left               # intent; prints the delta + new frame
uv run arcg snapshot base           # name the current state (= action sequence)
uv run arcg peek base               # view it from cache — free, no budget
uv run arcg restore base            # reset+replay back to it — costs budget
uv run arcg end                     # close scorecard, clear session
```

Commands are layered (`arcg/manifest.py`): **0** protocol (`start/act/end`) ·
**1** intent+perception (`move/interact/click/undo/look/diff`) · **2**
state+determinism (`history/snapshot/restore/peek`) · **3** memory (`note`).
Each layer imports strictly downward; only Layer 0 touches the API client
(enforced by `tests/test_layering.py`). The game is deterministic after RESET, so
a state *is* its action sequence — `restore` replays to it and verifies the
determinism holds.

## Baselines (non-agentic)

```bash
uv run arc3 --agent random --game ls20   # random floor: loses, scores 0
uv run arc3 --agent claude --game ls20   # programmatic Claude policy (JSON in/out)
```

## Layout

- `src/arc_agi_3/client.py` — REST client (auth, cookies, scorecard, game loop)
- `src/arc_agi_3/structs.py` — `FrameData`, `GameAction`, `GameState`, `Action`
- `src/arc_agi_3/agents/` — `base.Agent` (loop+verdict), `random_agent`
- `src/arc_agi_3/arcg/` — the layered `arcg` surface (manifest, store, layer0-3, cli)
- `src/arc_agi_3/client.py` · `perception.py` · `structs.py` — Layer 0/1 internals + vocabulary
- `src/arc_agi_3/session.py` — persisted session substrate
- `src/arc_agi_3/policy_claude.py` + `agents/llm_agent.py` + `main.py` — programmatic
  `arc3` policy (legacy; bypasses `arcg` — migration to the surface pending)
- `AGENT.md` — playbook handed to Claude when it plays via `arcg`
- `tests/` — offline proofs (layering, consistency, perception, session, loop, parser)
