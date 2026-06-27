"""The Action DAG as a pure data structure — the impl behind DAGGER.md §interface.

DRAFT, UNVERIFIED (see __init__). Every function below is a first cut whose correctness no drive
has tested. Known soft spots are marked inline. In particular: the matcher is exact-string-only,
the simmer commuting check is absent, and merge's status-conflict resolution is naive.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

WIN = "win game"   # the apex goal; the one node born undecomposed.
_MODES = ("sequence", "conjunction")
# Verdict precedence for the join. killed dominates (from-kill strictly dominates, PLAN.md
# §iteration-invariant); a status only ratchets up, never silently downgrades.
_STATUS_RANK = {"open": 0, "live": 1, "killed": 2}


def _norm(s: str | None) -> str:
    """Normalize a prose predicate to its exact-identity key (lowercase, collapse whitespace).
    This is the EXACT side of 'matcher for the predicate, exact equality for identity' — two
    spellings the matcher might judge equal stay distinct here by design (PLAN.md §strength)."""
    return " ".join((s or "").strip().lower().split())


@dataclass(frozen=True)
class Node:
    """A morphism: a goal from above (`post`), an action/transformation from below.

    A leaf carries a primitive `action` token and no children. A compound carries `children`
    (node ids) under a `mode`. `status` is the write-once verdict and is deliberately OUTSIDE the
    identity key so a kill leaves the ref stable.
    """

    post: str = ""                       # prose goal predicate (codomain)
    pre: str = ""                        # prose applicability (domain)
    action: str | None = None            # leaf only: the primitive action token (ACTION1..7)
    children: tuple[str, ...] = ()        # compound only: child node ids
    mode: str | None = None              # compound only: "sequence" | "conjunction"
    status: str = "open"                 # write-once verdict: open -> live | killed
    # TODO(drive): reliability schema lands here — support/success/failure counts, abstraction
    # version (codex's note). Drafted absent; discovered on the first JIT-miss drive.

    @property
    def is_leaf(self) -> bool:
        return self.action is not None

    @property
    def id(self) -> str:
        """Content-address over the NORMALIZED-EXACT defining fields (status excluded). Never a
        matcher call — identity is exact, the matcher only proposes edges (it must not dedup)."""
        key = "|".join([_norm(self.post), _norm(self.pre), self.action or "",
                        ",".join(self.children), self.mode or ""])
        return hashlib.sha1(key.encode()).hexdigest()[:10]

    def ref(self) -> str:
        return f"dagger:{self.id}"


@dataclass(frozen=True)
class Hole:
    """A JIT miss: `goal` has no cached decomposition. Handed to the reasoner to abduce children.
    A MISS is data (a place to grow the DAG), not an error."""

    goal: str


@dataclass
class Dag:
    """The Action DAG: nodes keyed by content-address id. Born with its two boundaries only
    (§initial-DAG); the middle is grown JIT where the two roots meet."""

    nodes: dict[str, Node] = field(default_factory=dict)


# --- verbs (the committed outer interface) --------------------------------
def init(actions) -> Dag:
    """Seed the DAG: apex `win game` (open, undecomposed) + one leaf per primitive action. Fully
    determined — no degrees of freedom. `actions` = the frame's available_actions tokens."""
    d = Dag()
    put(d, Node(post=WIN))                       # apex
    for a in actions:
        put(d, Node(action=a))                   # base: a primitive leaf (effect still open)
    return d


def put(dag: Dag, node: Node) -> Node:
    """Idempotent insert with content-addressed dedup; returns the canonical node. On an id
    collision the DOMINANT status wins (killed > live > open), so put is a join — order-
    independent, which is exactly what makes merge commutative + idempotent (the meet law).
    A status ratchets up, never down. (Deliberate verdict verbs kill/witness are still TODO;
    the join below is what merge needs to be lawful.)"""
    cur = dag.nodes.get(node.id)
    if cur is None or _STATUS_RANK[node.status] > _STATUS_RANK[cur.status]:
        dag.nodes[node.id] = node
        return node
    return cur


def get(dag: Dag, ref: str) -> Node | None:
    """Resolve a `dagger:<id>` ref (or a bare id) to its node, or None on MISS. This is what the
    dagger-gate's liveness reader calls once it is wired (see gates.py TODO)."""
    nid = ref[len("dagger:"):] if ref.startswith("dagger:") else ref
    return dag.nodes.get(nid)


def entails(post: str, pre: str) -> bool:
    """The MATCHER (a stub): does `post` satisfy `pre`? DRAFT = exact normalized-string match.

    This is the judged subsumption of DAGGER.md §soft-typing — prose, optionally simmer-checked,
    PROPOSE-ONLY (it must never key `put`'s dedup). Exact match will under-fire (every paraphrase
    misses); that is the intended floor until it mispredicts often enough to harden. UNVERIFIED.
    """
    return _norm(post) == _norm(pre)


def plan(dag: Dag, goal: str) -> Node | Hole:
    """JIT: return a cached, non-killed compound node whose `post` matches `goal` (a hit), else a
    HOLE to abduce. Match uses the matcher stub, so today only an exact prior decomposition hits."""
    for n in dag.nodes.values():
        if n.children and n.status != "killed" and entails(n.post, goal):
            return n
    return Hole(goal=goal)


def decompose(dag: Dag, goal: str, children, mode: str) -> Node:
    """Write a decomposition of `goal` into `children` (node ids) under `mode`. The commuting
    check `compose(children) ⊨ goal` is meant to be TESTED in simmer (§soft-typing) and localize
    the residual on a miss — NOT wired here. So this currently writes the node UNVERIFIED; the
    verdict stays `open` until a trial flips it. A malformed mode is a process-invariant bounce."""
    if mode not in _MODES:
        raise ValueError(f"dagger: mode must be one of {_MODES}, got {mode!r}")
    # TODO: achieve each child in simmer, check goal predicate fires; on miss, name the missing
    # child from the still-false residual and from-kill the decomposition with it.
    return put(dag, Node(post=goal, children=tuple(children), mode=mode))


def merge(a: Dag, b: Dag) -> Dag:
    """Union two DAGs. Commutative + idempotent (the meet law): merge(a,b) == merge(b,a) and
    merge(a,a) == a. Content-addressed ids make node-union a set union, and put resolves any
    status conflict by domination (killed > live > open), so insertion order doesn't matter."""
    out = Dag()
    for n in list(a.nodes.values()) + list(b.nodes.values()):
        put(out, n)
    return out


def live(node: Node | None) -> bool:
    """A node is live for the dagger-gate iff it exists and isn't killed. REACHABILITY in the DAG
    (the matcher-judged part of 'live') is NOT checked here — that is the deferred liveness from
    PLAN.md §strength (liveness = reachable, established by matcher-judged edges)."""
    return node is not None and node.status != "killed"
