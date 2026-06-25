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
uv run arcg games                       # list game ids
uv run arcg start ls20                  # open scorecard, reset, show frame
uv run arcg act ACTION3 --note "down?"  # act; prints the delta + new frame
uv run arcg act ACTION6 --x 12 --y 34   # complex/click action
uv run arcg status                      # state/score/step + notes
uv run arcg end                         # close scorecard, clear session
```

## Baselines (non-agentic)

```bash
uv run arc3 --agent random --game ls20   # random floor: loses, scores 0
uv run arc3 --agent claude --game ls20   # programmatic Claude policy (JSON in/out)
```

## Layout

- `src/arc_agi_3/client.py` — REST client (auth, cookies, scorecard, game loop)
- `src/arc_agi_3/structs.py` — `FrameData`, `GameAction`, `GameState`, `Action`
- `src/arc_agi_3/agents/` — `base.Agent` (loop+verdict), `random_agent`
- `src/arc_agi_3/tools.py` — `arcg` agent-facing tools (stateful session)
- `src/arc_agi_3/session.py` — persisted session (ids, grid, cookies, notes)
- `src/arc_agi_3/policy_claude.py` + `agents/llm_agent.py` — Claude policy
- `src/arc_agi_3/main.py` — `arc3` batch runner
- `AGENT.md` — playbook handed to Claude when it plays via `arcg`
- `tests/` — offline proofs (loop, perception, parser, session)
