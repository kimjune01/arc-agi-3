"""The Action DAG — verbs over the jotter SQLite store (the impl behind DAGGER.md §interface).

DRAFT, UNVERIFIED (see __init__). The store is the source of truth (`jotter.db`); a `Node` is the
in-memory shape, identified by an authored ANCHOR (write-once, like arbor's #4), not a hash of its
prose. `render` projects the whole graph to markdown for inspection; nothing parses prose back in.

Known soft spots, marked inline: the matcher is exact-string-only, the simmer commuting check is
absent, and structure is first-write-wins (no in-place revision; a real change is a from-kill).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..jotter import db
from ..session import STATE_DIR

WIN = "win game"        # the apex goal predicate (prose)
WIN_ANCHOR = "win-game"  # the apex's authored anchor
_MODES = ("sequence", "conjunction")


def _norm(s: str | None) -> str:
    """Normalize a prose predicate for the EXACT side of matching (lowercase, collapse space)."""
    return " ".join((s or "").strip().lower().split())


@dataclass(frozen=True)
class Node:
    """A morphism: a goal from above (`post`), an action/transformation from below. Identity is
    the authored `anchor`. A leaf carries a primitive `action`; a compound carries `children`
    (anchors) under a `mode`. `status` is the write-once verdict."""

    anchor: str
    post: str = ""
    pre: str = ""
    action: str | None = None
    children: tuple[str, ...] = ()
    mode: str | None = None
    status: str = "open"

    @property
    def is_leaf(self) -> bool:
        return self.action is not None

    @property
    def kind(self) -> str:
        return "leaf" if self.is_leaf else "compound"

    def ref(self) -> str:
        return f"dagger:{self.anchor}"


@dataclass(frozen=True)
class Hole:
    """A JIT miss: `goal` has no cached decomposition. Handed to the reasoner to abduce children.
    A MISS is data (a place to grow the DAG), not an error."""

    goal: str


def _to_dict(n: Node) -> dict:
    return {"anchor": n.anchor, "kind": n.kind, "pre": n.pre, "post": n.post,
            "action": n.action, "children": list(n.children), "mode": n.mode, "status": n.status}


def _from_dict(d: dict) -> Node:
    return Node(anchor=d["anchor"], post=d.get("post", ""), pre=d.get("pre", ""),
                action=d.get("action"), children=tuple(d.get("children", ())),
                mode=d.get("mode"), status=d.get("status", "open"))


# --- verbs (the committed outer interface) --------------------------------
def connect(path=None):
    """Open the graph store. Defaults to the session state dir; pass ':memory:' for tests."""
    return db.connect(STATE_DIR / "graph.db" if path is None else path)


def init(conn, actions):
    """Seed the DAG: apex `win game` (open, undecomposed) + one leaf per primitive action. Fully
    determined — the leaf's anchor is the action token. `actions` = the frame's available_actions."""
    put(conn, Node(anchor=WIN_ANCHOR, post=WIN))
    for a in actions:
        put(conn, Node(anchor=a, action=a))      # a primitive leaf (effect still open)
    return conn


def put(conn, node: Node) -> Node:
    """Idempotent insert keyed by anchor; status ratchets up by domination (db enforces it)."""
    return _from_dict(db.put(conn, _to_dict(node)))


def get(conn, ref: str) -> Node | None:
    """Resolve a `dagger:<anchor>` ref (or a bare anchor) to its node, or None on MISS. This is
    what the dagger-gate's liveness reader calls."""
    anchor = ref[len("dagger:"):] if ref.startswith("dagger:") else ref
    d = db.get(conn, anchor)
    return _from_dict(d) if d else None


def entails(post: str, pre: str) -> bool:
    """The MATCHER (a stub): does `post` satisfy `pre`? DRAFT = exact normalized-string match.
    The judged subsumption of DAGGER.md §soft-typing — prose, optionally simmer-checked,
    PROPOSE-ONLY (never keys identity). Exact match under-fires until it is hardened. UNVERIFIED."""
    return _norm(post) == _norm(pre)


def plan(conn, goal: str):
    """JIT: return a cached, non-killed compound node whose `post` matches `goal` (a hit), else a
    HOLE to abduce. Match uses the matcher stub, so only an exact prior decomposition hits today."""
    for d in db.nodes(conn):
        if d["children"] and d["status"] != "killed" and entails(d["post"], goal):
            return _from_dict(d)
    return Hole(goal=goal)


def decompose(conn, anchor: str, goal: str, children, mode: str) -> Node:
    """Write a decomposition of `goal` into `children` (child anchors) under `mode`, identified by
    the authored `anchor`. The commuting check `compose(children) ⊨ goal` is meant to be TESTED in
    simmer (§soft-typing) — NOT wired here, so this writes UNVERIFIED with status `open`. A
    malformed mode is a process-invariant bounce."""
    if mode not in _MODES:
        raise ValueError(f"dagger: mode must be one of {_MODES}, got {mode!r}")
    # TODO: achieve each child in simmer, check goal predicate fires; on miss name the missing
    # child from the still-false residual and from-kill the decomposition with it.
    return put(conn, Node(anchor=anchor, post=goal, children=tuple(children), mode=mode))


def merge(into_conn, from_conn):
    """Merge `from_conn`'s nodes into `into_conn`. The meet law: put's status domination makes it
    commutative + idempotent on the node set (killed > live > open wins regardless of order)."""
    for d in db.nodes(from_conn):
        db.put(into_conn, d)
    return into_conn


def live(node: Node | None) -> bool:
    """A node is live for the dagger-gate iff it exists and isn't killed. REACHABILITY in the DAG
    (the matcher-judged part of 'live') is NOT checked here — that is the deferred liveness from
    PLAN.md §strength (liveness = reachable, established by matcher-judged edges)."""
    return node is not None and node.status != "killed"


def render(conn) -> str:
    """Project the whole graph to markdown for inspection (db -> prose, one direction)."""
    return db.render(conn)
