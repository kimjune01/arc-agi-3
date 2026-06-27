"""dagger — the Action DAG (pmem): goal→action decompositions, JIT-on-miss.

DRAFT, UNVERIFIED. No drive has exercised this yet; correctness is a hypothesis, not a claim.
The committed outer interface and the two named holes (the matcher, the record schema) live in
DAGGER.md §interface. The matcher `⊨` is a stub (exact string match) and the simmer commuting
check is not wired. Expect this to be wrong in ways only a drive will surface.
"""

from .dag import (
    WIN,
    Dag,
    Hole,
    Node,
    decompose,
    entails,
    get,
    init,
    live,
    merge,
    plan,
    put,
)

__all__ = [
    "WIN", "Dag", "Hole", "Node",
    "decompose", "entails", "get", "init", "live", "merge", "plan", "put",
]
