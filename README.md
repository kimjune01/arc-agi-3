# arc-agi-3

Research toward an agent that plays the **ARC-AGI-3** interactive reasoning
benchmark — small games where the agent learns the rules by acting, aiming to
reach a `WIN` state. Research log and API ground truth: [`NOTES.md`](./NOTES.md).

## Setup

```bash
uv sync
cp .env.example .env      # then paste your free key from three.arcprize.org
```

## Entrypoints

Seven `uv run` commands, each a thin CLI over one module. They share state through
`ARCG_STATE_DIR` (default `.arc/`), so one run's game, world-model, and memory are one
shared substrate. Pull specifics from `uv run <cmd> --help`.

| command  | role | key verbs |
|----------|------|-----------|
| `arcg`   | **the hands** — stateful game surface (the only thing that spends budget) | `start` · `act`/`move`/`interact`/`click` · `look`/`diff` · `snapshot`/`restore`/`peek` · `note` · `end` |
| `simmer` | **the world model** — free forward prediction (plan here, commit in `arcg`) | `predict` · `test` · `step` |
| `jotter` | **episodic memory** — the grounded transition corpus | `stats` · `effects` · `trace` · `pending` · `spend` · `evict` · `show` |
| `dagger` | **procedural memory** — the Action DAG of goal→action decompositions | `render` · `plan` · `decompose` · `get` · `init` |
| `drive`  | **the loop** (programmatic) — gated serial exploit/explore over the above | `drive ls20 --budget 25 [--goal ... --max-steps N]` |
| `reason` | **the loop** (agentic) — Claude-Code as reasoner, alternating wake/sleep | `reason ls20 --units N --cycles N --budget N [--checkpoint DIR]` |
| `arc3`   | **baselines** (legacy, non-agentic) — random / programmatic-Claude policy | `arc3 --agent random|claude --game ls20` |

## Play

**Agentic, hand-driven** — point a fresh Claude at the playbook and let it call `arcg`:

```bash
claude "Read AGENT.md, then play ls20 with the arcg tools until WIN or GAME_OVER."
```

The session (ids, grid, affinity cookies, notes) persists in `.arc/session.json` between
calls, so each command continues the same game. `arcg` is layered (`arcg/manifest.py`):
**0** protocol (`start/act/end`) · **1** intent+perception (`move/interact/click/undo/look/diff`)
· **2** state+determinism (`history/snapshot/restore/peek`) · **3** memory (`note`). Each layer
imports strictly downward; only Layer 0 touches the API client (enforced by `tests/test_layering.py`).
The game is deterministic after RESET, so a state *is* its action sequence — `restore` replays to
it and verifies the determinism holds.

**Self-driving** — the wake/sleep harness drives the whole loop itself:

```bash
uv run reason ls20 --units 4 --budget 20 --checkpoint checkpoints/ls20-firstpoint
```

It alternates WAKE passes (explore, act, record to jotter) with a SLEEP pass (consolidate
episodes into dagger), resuming durable memory from a checkpoint so learning compounds.

## Layout

Organized by the role each part plays in the loop (`perceive → predict → act → reconcile → note`):

**The hands** — `arcg/` the layered game surface: `layer0_protocol` (API) · `layer1_intent` +
`perception.py` (move/look/diff) · `layer2_state` (snapshot/restore) · `layer3_memory` (note) ·
`manifest`, `store`, `trace`, `gates`, `cli`.

**The world model** — `simmer/`: `engine.py` (the prior-free forward model) · `cli` (predict/test/step).

**Episodic memory** — `jotter/`: `graph.py` (content-addressed state/transition graph, dedup,
eviction) · `db.py` (the SQLite node store) · `cli`.

**Procedural memory** — `dagger/`: `dag.py` (the Action DAG — goal→action decompositions, JIT-on-miss,
graded confidence; the retention stub lives here) · `cli`. Design: [`DAGGER.md`](./DAGGER.md).

**The loop** — `driver/loop.py` (programmatic exploit/explore, `decide`+`run`) ·
`agents/reasoner.py` (the agentic wake/sleep harness).

**Substrate** — `client.py` (REST: auth, cookies, scorecard) · `structs.py` (`FrameData`,
`GameAction`, `GameState`, `Action`) · `session.py` (persisted run state) · `perception.py` (vocabulary).

**Baselines (legacy)** — `main.py` + `policy_claude.py` + `agents/{base,random_agent,llm_agent}.py`:
the non-agentic `arc3` policy that bypasses `arcg` (migration to the surface pending).

**Tests** — `tests/`: offline proofs (layering, consistency, perception, session, loop, dagger, jotter, simmer).

## Docs

- [`EXPLAINER.md`](./EXPLAINER.md) — the map for a fresh Claude about to play: the loop, tools, principles
- [`AGENT.md`](./AGENT.md) — the playbook handed to Claude when it plays via `arcg`
- [`PLAN.md`](./PLAN.md) — the architecture and its rationale
- [`DAGGER.md`](./DAGGER.md) — the Action DAG (procedural memory) design
- [`NOTES.md`](./NOTES.md) — research log and ARC-AGI-3 API ground truth
- [`WORKLOG.md`](./WORKLOG.md) — dated build log (rotates to `WORKLOG.1.md`)

## License

Dual, by kind:

- **Code** — [AGPL-3.0](./LICENSE): network use is distribution (§13).
- **Prose & docs** (`*.md`) — [CC BY-SA-NS](./LICENSE-CONTENT.md): CC BY-SA 4.0
  plus a Network Services clause — the same network-copyleft, for prose.
