"""dagger — the Action DAG (pmem): goal→action decompositions, JIT-on-miss.

DRAFT, UNVERIFIED. No drive has exercised this yet; correctness is a hypothesis, not a claim.
Verbs run over the jotter SQLite store (the db is truth; `render` projects it to markdown for
inspection). Node identity is the authored anchor, not a prose hash. The committed outer interface
and the two named holes (the matcher, the belief schema) live in DAGGER.md §interface. The matcher
`⊨` is a stub (exact string) and the simmer commuting check is not wired.
"""

from .dag import (
    COMMITTED,
    DEPOSIT_ANCHOR,
    DEPOSIT_POST,
    FREE,
    PAID,
    WIN,
    WIN_ANCHOR,
    Hole,
    Node,
    actionable,
    closure,
    confidence,
    connect,
    decompose,
    entails,
    get,
    init,
    live,
    merge,
    plan,
    put,
    render,
)

__all__ = [
    "WIN", "WIN_ANCHOR", "DEPOSIT_ANCHOR", "DEPOSIT_POST", "FREE", "PAID", "COMMITTED", "Hole", "Node",
    "actionable", "closure", "confidence", "connect", "decompose", "entails", "get", "init", "live",
    "merge", "plan", "put", "render",
]
