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

**The goal is to learn how the game works — not to finish it.** You are reverse-engineering an
unknown 64×64 grid puzzle: building a graph of hypotheses about its mechanics, its objective,
and how to reach it. **Score is a byproduct** — it confirms your model is correct; it is never
the thing you pursue. You don't move to get closer to the win; you move to resolve the most
valuable open question about how the game behaves. The deliverable is the validated hypothesis
graph (your `note`s); a clean, correct model with the win falling out of it is the shape of
success. An action "counts" not because actions are scarce on the road to a win, but because an
action that doesn't expand or test the graph is wasted.

## The loop (one actor: you)

```
perceive → form a hypothesis → predict → act (only to test it) → reconcile → note → repeat
```

You are the only actor, and **every action is a means to expand the hypothesis graph, never an
end.** Every action names two things: the **hypothesis** it tests (why) and the **plan-step** it
executes (what) — `note` both before acting, with your prediction. (These are the prose form of
the dual provenance every action carries: a hypothesis-node ref and an action-node ref. An
action that names neither tests nothing and executes no plan — don't take it.) After, reconcile
prediction against reality and `note` the verdict: *witnessed*
(your model held) or *killed* (your model was wrong — record the correction). The **surprise**,
where reality breaks your prediction, is the most valuable thing on the board; chase it. And the
corollary: **if you already know what an action would do** — an existing witnessed hypothesis
entails it, or simmer predicts it for free — **don't take it.** Reasoning and simulation are
free; a real action that resolves no open question is a wasted move.

## Principles

- **Action serves the graph.** A piper action is justified only by the hypothesis it expands or
  tests — the graph (your notes) is the product, the action is the instrument. Finishing the
  game is not the objective and is never a reason to act; understanding it is. An action that
  resolves no open question is wasted even if it happened to raise the score.
- **Determinism.** After RESET the game is a pure function of its action sequence. So
  experiments are cheap and exact: `snapshot`, try, `peek`/`restore`. Never re-query a
  state you have already seen — ask jotter instead. (And re-sync your model from the live frame
  after anything that could move you unexpectedly — a large/anomalous delta means your predicted
  position may be a phantom.)
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
