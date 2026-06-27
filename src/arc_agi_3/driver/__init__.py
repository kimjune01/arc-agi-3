"""driver — the synchronous serial loop (PLAN.md §the-serial-loop).

One step at a time, no actors, no queues. It ties the built pieces together: perceive
(piper.look), predict for free (simmer.step), act through the GATED commit path (piper.act ->
dagger/arbor pregates -> jotter record -> postgate reconcile), and decide where to spend the next
paid action.

This is the SKELETON. The cognitive steps it leaves as TODO are the belief layer we keep deferred:
arbor abduce/witness on surprise, and dagger.decompose to grow real plans. The loop runs without
them by exploring: it uses the free simmer to avoid spending budget on a predicted no-op, names the
real dagger leaf for each action (so the dual-provenance ref resolves in the store), and records
every surprise (piper XOR simmer) for the reasoner to consolidate later.
"""

from .loop import decide, run

__all__ = ["decide", "run"]
