# Drive: playing ARC-AGI-3

Session opener for a fresh `claude` that will play the game. This is the **map**, not
the manual: it names the loop, the tools, and the principles, and defers every *how* to
`<tool> --help` and [AGENT.md](AGENT.md). Read it once, then play.

## 0. Claim a run dir

Each drive gets its own state dir under `/tmp` so runs never collide. At the top, once:

```bash
RUN=$(bin/claim-run.sh)        # or: bin/claim-run.sh <N> to pick/resume a run number
```

`claim-run.sh` prints the dir (e.g. `/tmp/arcg-run3`) on stdout; capture it as `RUN`.
Shell state does not persist between commands here, so carry it literally every call:

```bash
ARCG_STATE_DIR=$RUN uv run --project <repo> arcg  <cmd> ...
ARCG_STATE_DIR=$RUN uv run --project <repo> simmer <cmd> ...
ARCG_STATE_DIR=$RUN uv run --project <repo> jotter <cmd> ...
```

All three modules read the same `ARCG_STATE_DIR`, so piper's corpus, simmer's tests,
and jotter's graph are one shared run.

## The goal

You are playing an unknown 64×64 grid puzzle. The rules are not given. **Learn them by
acting and watching the delta.** Drive `score` to the win target in the fewest actions —
scoring is efficiency, so every real action counts.

## The loop (one actor: you)

```
perceive → predict in-head → act (or experiment for free) → reconcile → note → plan → repeat
```

You are the only actor. The modules are your instrument panel; you do the attending and
deciding. Predict in simmer or in your head, commit the irreducible step in piper, and
reconcile the two by diffing.

## Principles

- **Determinism.** After RESET the game is a pure function of its action sequence. So
  experiments are cheap and exact: `snapshot`, try, `peek`/`restore`. Never re-query a
  state you have already seen — ask jotter instead.
- **Budget.** piper actions are the only spend; reasoning and simmer are free. Spend a
  real action only when a free rollout is untrustworthy. The sharpest case is a move that
  is both *novel* (jotter has never reached the result) and *surprising* (simmer can't
  predict it). Reason for free; pay for the irreducible.
- **Figure/ground.** The delta is the signal. What changed localizes the *effect* of your
  action (which may be local, remote, or on a status meter) and names what the action did.
  Zero change means you acted on an inert region, not necessarily a wall.

## Tool → role

| tool | role | cost | reference |
| --- | --- | --- | --- |
| **piper** (`arcg`) | the REAL game: perceive (`look`/`objects`/`diff`), act (whichever ACTIONs the frame offers — `move`/`interact`/`click`/`undo`), determinism (`snapshot`/`peek`/`restore`), `note`, `start`/`end` | budget | `arcg --help`, [AGENT.md](AGENT.md) |
| **simmer** | your hand-written model of *this* game. When you learn a mechanic, write it into the engine; `simmer test` replays piper's corpus to check the edit. Predict here, commit in piper, diff the two. The shipped engine models a *movement* game — a different game (click/select/configure) needs a fresh model, or none if you can reason in-head. | free | `simmer --help` |
| **jotter** | content-addressed memory of every state reached. `jotter has <hash>` (known/novel), `jotter stats`, `jotter audit` (reconciles vs piper's budget). | free | `jotter --help` |

simmer's engine is **meant to be hand-edited** — you are the compiler. A bad edit surfaces
as a failed `simmer test`, localized to the cells it got wrong. Edit freely; the test
secures it.

## Start

1. `bin/claim-run.sh`, `arcg start <game>`, then `arcg look` + `arcg objects` on the static
   frame. Read the **available actions** the frame reports — they tell you what kind of game
   this is (moves? a single `click`? selects?). Do not assume navigation.
2. **Discover the interactive surface first.** Before theorizing the goal, find which regions
   are controls: probe one representative cell of each salient region with a single action and
   diff. A change means "this is a control" (note where its effect landed — it may be elsewhere);
   no change means "inert region", not a wall. Map the controls before guessing the objective.
3. **Name the win-model** as a branch point and `note` it: is victory a *path* (reach a place),
   a *configuration to match*, a *selection/toggle*, or a *sequence*? Pick by what the board
   affords, not by assuming a route. `score X/N` often means N independent sub-conditions.
4. From there each action is a hypothesis test aimed at the guessed goal, not a coin flip:
   predict the effect, act once, diff, `note` what you learned. The loop is running.
5. Stop at WIN/GAME_OVER, then `arcg end`.
