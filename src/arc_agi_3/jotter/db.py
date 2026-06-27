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
  status   TEXT NOT NULL DEFAULT 'open'  -- write-once verdict: open -> live | killed
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
    return conn


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["children"] = json.loads(d["children"])
    return d


def put(conn: sqlite3.Connection, node: dict) -> dict:
    """Idempotent upsert keyed by anchor. On conflict the DOMINANT status wins (killed > live >
    open) and structure is left as first-written (write-once). Returns the canonical row.

    `INSERT ... ON CONFLICT DO UPDATE WHERE rank(new) > rank(old)` IS the set-add join: re-putting
    the same anchor is a no-op unless the verdict ratchets up. The PK makes idempotency structural.
    """
    conn.execute(
        f"""INSERT INTO nodes (anchor, kind, pre, post, action, children, mode, status)
            VALUES (:anchor, :kind, :pre, :post, :action, :children, :mode, :status)
            ON CONFLICT(anchor) DO UPDATE SET status = excluded.status
              WHERE ({_RANK.format(s='excluded.status')}) > ({_RANK.format(s='nodes.status')})""",
        {
            "anchor": node["anchor"], "kind": node["kind"],
            "pre": node.get("pre", "") or "", "post": node.get("post", "") or "",
            "action": node.get("action"), "mode": node.get("mode"),
            "children": json.dumps(list(node.get("children", []))),
            "status": node.get("status", "open"),
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
        lines.append(f"## {d['anchor']}  [{d['kind']}, {d['status']}]")
        if d["post"]:
            lines.append(f"- post: {d['post']}")
        if d["pre"]:
            lines.append(f"- pre: {d['pre']}")
        if d["action"]:
            lines.append(f"- action: {d['action']}")
        if d["children"]:
            lines.append(f"- {d['mode']}: {' ; '.join(d['children'])}")
        lines.append("")
    return "\n".join(lines).rstrip()
