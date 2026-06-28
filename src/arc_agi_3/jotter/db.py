"""jotter/db.py — the lightweight structured store (SQLite) for the graph memory.

Single file, stdlib `sqlite3`, no server (single-agent serial; correctness over wall-clock).
This is the "lightweight db as a jotter submodule": it holds the node graph (dagger now, arbor
later). The transition corpus stays in jsonl; this is the structured layer above it.

Discipline (load-bearing): the DB is the source of truth, `render` projects it to legible
markdown for inspection, and truth flows DB -> prose, never prose -> DB. Identity is the
authored ANCHOR (the write-once ref), not a hash of the prose; the prose is annotation. There is
deliberately no parser back from the rendered markdown. Belief (verdicts, credence) is a deferred
derived query, not a baked column — this schema is the evidence/skeleton only.

db.py is dagger-agnostic on purpose (it knows the node TABLE, not the matcher/plan semantics), so
it stays below dagger in the import order (dagger imports jotter, never the reverse).
"""

from __future__ import annotations

import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
  anchor   TEXT PRIMARY KEY,             -- write-once id / ref (dagger:<anchor>), authored not hashed
  kind     TEXT NOT NULL,                -- 'leaf' | 'compound'
  pre      TEXT NOT NULL DEFAULT '',     -- prose applicability (domain)
  post     TEXT NOT NULL DEFAULT '',     -- prose goal predicate (codomain)
  action   TEXT,                         -- leaf: the primitive action token
  children TEXT NOT NULL DEFAULT '[]',   -- compound: JSON list of child anchors
  mode     TEXT,                         -- compound: 'sequence' | 'conjunction'
  status   TEXT NOT NULL DEFAULT 'open', -- write-once verdict: open -> live | killed
  evidence TEXT NOT NULL DEFAULT '[]'    -- JSON list of jotter episode/state refs this post is attributed to
);
"""

# Verdict precedence for the join. killed dominates (from-kill strictly dominates); a status
# ratchets up, never down. Inlined as a CASE so the domination is enforced in the ON CONFLICT.
_RANK = ("CASE {s} WHEN 'open' THEN 0 WHEN 'live' THEN 1 WHEN 'killed' THEN 2 ELSE 0 END")


def connect(path) -> sqlite3.Connection:
    """Open (creating if needed) the node store. `path` may be ':memory:' for tests."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Migrate a pre-evidence store in place: CREATE IF NOT EXISTS won't add a new column to an
    # existing table, so back-fill it. Legacy nodes default to '[]' (= speculative), the honest
    # classification for structure written before attribution was tracked.
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(nodes)")}
    if "evidence" not in cols:
        conn.execute("ALTER TABLE nodes ADD COLUMN evidence TEXT NOT NULL DEFAULT '[]'")
        conn.commit()
    return conn


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["children"] = json.loads(d["children"])
    d["evidence"] = json.loads(d.get("evidence") or "[]")
    return d


def put(conn: sqlite3.Connection, node: dict) -> dict:
    """Idempotent upsert keyed by anchor. On conflict the DOMINANT status wins (killed > live >
    open). Returns the canonical row.

    `INSERT ... ON CONFLICT DO UPDATE WHERE rank(new) > rank(old)` IS the set-add join: re-putting
    the same anchor is a no-op unless the verdict ratchets UP. The PK makes idempotency structural.

    A status ratchet carries the GROUNDING with it: `evidence` is adopted from the winning put, and
    empty structure (children/mode/post seeded blank) is FILLED — so the dream->verdict lifecycle
    works (an `open` node promoted to a `killed`/`live` verdict records the contrast pair it cites,
    instead of silently keeping the open node's empty evidence). NON-empty structure stays
    write-once: once a node has children/post, a later ratchet can't rewrite them.
    """
    conn.execute(
        f"""INSERT INTO nodes (anchor, kind, pre, post, action, children, mode, status, evidence)
            VALUES (:anchor, :kind, :pre, :post, :action, :children, :mode, :status, :evidence)
            ON CONFLICT(anchor) DO UPDATE SET
                status   = excluded.status,
                evidence = excluded.evidence,
                children = CASE WHEN nodes.children = '[]' THEN excluded.children ELSE nodes.children END,
                mode     = CASE WHEN COALESCE(nodes.mode, '') = '' THEN excluded.mode ELSE nodes.mode END,
                post     = CASE WHEN nodes.post = '' THEN excluded.post ELSE nodes.post END,
                kind     = CASE WHEN nodes.children = '[]' AND nodes.action IS NULL
                                THEN excluded.kind ELSE nodes.kind END
              WHERE ({_RANK.format(s='excluded.status')}) > ({_RANK.format(s='nodes.status')})""",
        {
            "anchor": node["anchor"], "kind": node["kind"],
            "pre": node.get("pre", "") or "", "post": node.get("post", "") or "",
            "action": node.get("action"), "mode": node.get("mode"),
            "children": json.dumps(list(node.get("children", []))),
            "status": node.get("status", "open"),
            "evidence": json.dumps(list(node.get("evidence", []))),
        },
    )
    conn.commit()
    return get(conn, node["anchor"])


def get(conn: sqlite3.Connection, anchor: str) -> dict | None:
    r = conn.execute("SELECT * FROM nodes WHERE anchor = ?", (anchor,)).fetchone()
    return _row(r) if r else None


def nodes(conn: sqlite3.Connection) -> list[dict]:
    return [_row(r) for r in conn.execute("SELECT * FROM nodes ORDER BY anchor").fetchall()]


def render(conn: sqlite3.Connection) -> str:
    """Project the whole graph to legible markdown for inspection (db -> prose, one direction)."""
    rows = nodes(conn)
    if not rows:
        return "# dagger graph (empty)"
    lines = [f"# dagger graph ({len(rows)} nodes)", ""]
    for d in rows:
        # A compound is a claim: mark it grounded (cites episodes) or speculative (a dream, no
        # evidence yet). Leaves are primitives, not claims, so they carry no provenance tag.
        prov = ""
        if d["kind"] == "compound":
            prov = ", grounded" if d["evidence"] else ", speculative"
        lines.append(f"## {d['anchor']}  [{d['kind']}, {d['status']}{prov}]")
        if d["post"]:
            lines.append(f"- post: {d['post']}")
        if d["pre"]:
            lines.append(f"- pre: {d['pre']}")
        if d["action"]:
            lines.append(f"- action: {d['action']}")
        if d["children"]:
            lines.append(f"- {d['mode']}: {' ; '.join(d['children'])}")
        if d["evidence"]:
            lines.append(f"- evidence: {', '.join(d['evidence'])}")
        lines.append("")
    return "\n".join(lines).rstrip()
