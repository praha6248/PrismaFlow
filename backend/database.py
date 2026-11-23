"""SQLite workspace: schema, connection handling and typed data access."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 8

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    seed TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    geo TEXT NOT NULL DEFAULT '',
    phase TEXT NOT NULL DEFAULT 'discover',
    stage TEXT NOT NULL DEFAULT 'compose',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    kind TEXT CHECK (kind IN ('niche', 'idea', 'target_group', 'pain_point', 'competitor')),
    is_root INTEGER NOT NULL DEFAULT 0,
    starred INTEGER NOT NULL DEFAULT 0,
    origin TEXT NOT NULL DEFAULT 'user' CHECK (origin IN ('user', 'ai')),
    search_query TEXT,
    score REAL NOT NULL DEFAULT 0,
    trend_growth REAL,
    trend_series TEXT,
    enriched_at REAL,
    x REAL,
    y REAL,
    created_at REAL NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS nodes_project_label ON nodes(project_id, label COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS nodes_project ON nodes(project_id);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    origin TEXT NOT NULL DEFAULT 'user',
    created_at REAL NOT NULL,
    CHECK (source_id <> target_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS edges_unique ON edges(project_id, MIN(source_id, target_id), MAX(source_id, target_id));
CREATE INDEX IF NOT EXISTS edges_project ON edges(project_id);

CREATE TABLE IF NOT EXISTS api_cache (
    key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    payload TEXT NOT NULL,
    fetched_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS api_cache_source ON api_cache(source);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    node_id INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('autocomplete', 'community', 'reddit', 'trends', 'llm')),
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    url TEXT,
    weight REAL NOT NULL DEFAULT 0,
    meta TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS evidence_unique ON evidence(node_id, source, title);
CREATE INDEX IF NOT EXISTS evidence_node ON evidence(node_id);

CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
    title,
    body,
    source UNINDEXED,
    content='evidence',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS evidence_vectors (
    evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    vector BLOB NOT NULL,
    PRIMARY KEY (evidence_id, model)
);

CREATE TABLE IF NOT EXISTS query_vectors (
    model TEXT NOT NULL,
    query TEXT NOT NULL,
    vector BLOB NOT NULL,
    PRIMARY KEY (model, query)
);

CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    keyword TEXT NOT NULL,
    quote TEXT,
    quote_source TEXT,
    node_ids TEXT NOT NULL DEFAULT '[]',
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    trend TEXT,
    chosen INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS problems_project ON problems(project_id);

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    problem_id INTEGER NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    age INTEGER,
    role TEXT NOT NULL DEFAULT '',
    quote TEXT NOT NULL DEFAULT '',
    options TEXT NOT NULL DEFAULT '[]',
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    profile TEXT NOT NULL DEFAULT '{}',
    chosen_option INTEGER,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS personas_problem ON personas(problem_id);

CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    priority TEXT NOT NULL CHECK (priority IN ('must', 'should', 'could', 'wont')),
    position INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '[]',
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    support INTEGER NOT NULL DEFAULT 0,
    pool INTEGER NOT NULL DEFAULT 0,
    demand INTEGER NOT NULL DEFAULT 0,
    origin TEXT NOT NULL DEFAULT 'ai' CHECK (origin IN ('user', 'ai')),
    impact REAL NOT NULL DEFAULT 1,
    effort REAL NOT NULL DEFAULT 2,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS features_project ON features(project_id);

CREATE TABLE IF NOT EXISTS flows (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    suggestions TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS validations (
    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('board', 'empathy', 'tests')),
    data TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (project_id, kind)
);

CREATE TRIGGER IF NOT EXISTS evidence_ai AFTER INSERT ON evidence BEGIN
    INSERT INTO evidence_fts(rowid, title, body, source) VALUES (new.id, new.title, new.body, new.source);
END;

CREATE TRIGGER IF NOT EXISTS evidence_ad AFTER DELETE ON evidence BEGIN
    INSERT INTO evidence_fts(evidence_fts, rowid, title, body, source) VALUES ('delete', old.id, old.title, old.body, old.source);
END;

CREATE TRIGGER IF NOT EXISTS evidence_au AFTER UPDATE ON evidence BEGIN
    INSERT INTO evidence_fts(evidence_fts, rowid, title, body, source) VALUES ('delete', old.id, old.title, old.body, old.source);
    INSERT INTO evidence_fts(rowid, title, body, source) VALUES (new.id, new.title, new.body, new.source);
END;
"""

NODE_COLUMNS = (
    "id, project_id, label, kind, is_root, starred, origin, search_query, score, "
    "trend_growth, trend_series, enriched_at, x, y, created_at"
)


def _row_to_node(row: sqlite3.Row) -> dict[str, Any]:
    node = dict(row)
    node["is_root"] = bool(node["is_root"])
    node["starred"] = bool(node["starred"])
    series = node.pop("trend_series")
    node["trend_series"] = json.loads(series) if series else None
    return node


class Database:
    """Thin thread-safe wrapper around a SQLite workspace file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path) if str(path) != ":memory:" else path
        self._lock = threading.RLock()
        self._memory: sqlite3.Connection | None = None
        if self.path == ":memory:":
            self._memory = self._open()
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection inside a transaction that commits on success."""
        with self._lock:
            conn = self._memory or self._open()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                if conn is not self._memory:
                    conn.close()

    def migrate(self) -> None:
        """Create or upgrade the schema."""
        with self.connect() as conn:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'evidence'").fetchone()
            rebuild = bool(row) and "'community'" not in row["sql"]
            if rebuild:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("ALTER TABLE evidence RENAME TO evidence_old")
            conn.executescript(SCHEMA)
            persona_columns = {r["name"] for r in conn.execute("PRAGMA table_info(personas)")}
            if "profile" not in persona_columns:
                conn.execute("ALTER TABLE personas ADD COLUMN profile TEXT NOT NULL DEFAULT '{}'")
            if "evidence_ids" not in persona_columns:
                conn.execute("ALTER TABLE personas ADD COLUMN evidence_ids TEXT NOT NULL DEFAULT '[]'")
            feature_columns = {r["name"] for r in conn.execute("PRAGMA table_info(features)")}
            if "impact" not in feature_columns:
                conn.execute("ALTER TABLE features ADD COLUMN impact REAL NOT NULL DEFAULT 1")
            if "effort" not in feature_columns:
                conn.execute("ALTER TABLE features ADD COLUMN effort REAL NOT NULL DEFAULT 2")
            if rebuild:
                conn.execute("INSERT INTO evidence SELECT * FROM evidence_old")
                conn.execute("DROP TABLE evidence_old")
                conn.executescript(SCHEMA)
                conn.execute("INSERT INTO evidence_fts(evidence_fts) VALUES ('rebuild')")
                conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(SCHEMA_VERSION),),
            )

    def create_project(self, seed: str, language: str, geo: str) -> dict[str, Any]:
        """Create a project together with its root niche node."""
        now = time.time()
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects(name, seed, language, geo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (seed, seed, language, geo, now, now),
            )
            project_id = cur.lastrowid
            conn.execute(
                "INSERT INTO nodes(project_id, label, kind, is_root, origin, search_query, score, x, y, created_at) "
                "VALUES (?, ?, 'niche', 1, 'user', ?, 1, 0, 0, ?)",
                (project_id, seed, seed, now),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        """Return a project row or None."""
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def list_projects(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent projects, newest first."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT p.*, (SELECT COUNT(*) FROM nodes n WHERE n.project_id = p.id) AS node_count "
                "FROM projects p ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_project(self, project_id: int, **fields: Any) -> dict[str, Any] | None:
        """Update selected project columns."""
        allowed = {k: v for k, v in fields.items() if k in {"name", "stage", "phase", "language", "geo"} and v is not None}
        with self.connect() as conn:
            if allowed:
                assignments = ", ".join(f"{k} = ?" for k in allowed)
                conn.execute(
                    f"UPDATE projects SET {assignments}, updated_at = ? WHERE id = ?",
                    (*allowed.values(), time.time(), project_id),
                )
        return self.get_project(project_id)

    def touch_project(self, conn: sqlite3.Connection, project_id: int) -> None:
        """Bump a project's modification time inside an open transaction."""
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (time.time(), project_id))

    def delete_project(self, project_id: int) -> None:
        """Delete a project and everything attached to it."""
        with self.connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def list_nodes(self, project_id: int) -> list[dict[str, Any]]:
        """Return every node of a project."""
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT {NODE_COLUMNS} FROM nodes WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
        return [_row_to_node(r) for r in rows]

    def get_node(self, node_id: int) -> dict[str, Any] | None:
        """Return a single node or None."""
        with self.connect() as conn:
            row = conn.execute(f"SELECT {NODE_COLUMNS} FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return _row_to_node(row) if row else None

    def find_node(self, project_id: int, label: str) -> dict[str, Any] | None:
        """Find a node by case-insensitive label."""
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT {NODE_COLUMNS} FROM nodes WHERE project_id = ? AND label = ? COLLATE NOCASE",
                (project_id, label),
            ).fetchone()
        return _row_to_node(row) if row else None

    def root_node(self, project_id: int) -> dict[str, Any]:
        """Return the project's root niche node."""
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT {NODE_COLUMNS} FROM nodes WHERE project_id = ? AND is_root = 1", (project_id,)
            ).fetchone()
        if row is None:
            raise LookupError(f"project {project_id} has no root node")
        return _row_to_node(row)

    def insert_node(
        self,
        project_id: int,
        label: str,
        *,
        kind: str | None = None,
        origin: str = "user",
        search_query: str | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> dict[str, Any]:
        """Insert a node, returning the existing one when the label is already taken."""
        existing = self.find_node(project_id, label)
        if existing:
            return existing
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO nodes(project_id, label, kind, origin, search_query, x, y, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, label, kind, origin, search_query or label, x, y, time.time()),
            )
            self.touch_project(conn, project_id)
            node_id = cur.lastrowid
        return self.get_node(node_id)

    def update_node(self, node_id: int, **fields: Any) -> dict[str, Any] | None:
        """Update selected node columns."""
        allowed_keys = {"label", "kind", "starred", "x", "y", "score", "trend_growth", "search_query", "enriched_at"}
        values: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed_keys or value is None:
                continue
            values[key] = int(value) if key == "starred" else value
        if "trend_series" in fields and fields["trend_series"] is not None:
            values["trend_series"] = json.dumps(fields["trend_series"])
        if values:
            with self.connect() as conn:
                assignments = ", ".join(f"{k} = ?" for k in values)
                conn.execute(f"UPDATE nodes SET {assignments} WHERE id = ?", (*values.values(), node_id))
        return self.get_node(node_id)

    def update_positions(self, positions: list[tuple[int, float, float]]) -> None:
        """Persist layout coordinates for many nodes at once."""
        with self.connect() as conn:
            conn.executemany("UPDATE nodes SET x = ?, y = ? WHERE id = ?", [(x, y, i) for i, x, y in positions])

    def delete_node(self, node_id: int) -> None:
        """Delete a non-root node with its edges and evidence."""
        with self.connect() as conn:
            conn.execute("DELETE FROM nodes WHERE id = ? AND is_root = 0", (node_id,))

    def list_edges(self, project_id: int) -> list[dict[str, Any]]:
        """Return every edge of a project."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, project_id, source_id, target_id, origin FROM edges WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_edge(self, project_id: int, source_id: int, target_id: int, origin: str = "user") -> dict[str, Any] | None:
        """Insert an undirected edge unless it already exists."""
        if source_id == target_id:
            return None
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO edges(project_id, source_id, target_id, origin, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, source_id, target_id, origin, time.time()),
            )
            row = conn.execute(
                "SELECT id, project_id, source_id, target_id, origin FROM edges WHERE project_id = ? "
                "AND MIN(source_id, target_id) = MIN(?, ?) AND MAX(source_id, target_id) = MAX(?, ?)",
                (project_id, source_id, target_id, source_id, target_id),
            ).fetchone()
        return dict(row) if row else None

    def add_evidence(
        self,
        project_id: int,
        node_id: int,
        source: str,
        title: str,
        body: str = "",
        url: str | None = None,
        weight: float = 0.0,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Store one evidence item, ignoring duplicates for the same node."""
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO evidence(project_id, node_id, source, title, body, url, weight, meta, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, node_id, source, title, body, url, weight, json.dumps(meta or {}), time.time()),
            )

    def evidence_by_ids(self, ids: list[int]) -> list[dict[str, Any]]:
        """Return evidence items in the order of the given ids, skipping unknown ones."""
        if not ids:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT id, source, title, body, url, meta FROM evidence WHERE id IN ({','.join('?' * len(ids))})", ids
            ).fetchall()
        by_id = {r["id"]: {**dict(r), "meta": json.loads(r["meta"])} for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def list_evidence(self, node_id: int) -> list[dict[str, Any]]:
        """Return evidence attached to a node, strongest first."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, source, title, body, url, weight, meta FROM evidence WHERE node_id = ? "
                "ORDER BY weight DESC, id",
                (node_id,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["meta"] = json.loads(item["meta"])
            items.append(item)
        return items

    def search_evidence(self, project_id: int, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Full-text search over a project's evidence."""
        terms = [t for t in "".join(c if c.isalnum() else " " for c in query).split() if t]
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT e.id, e.node_id, e.source, e.title, e.body, e.url, e.weight, bm25(evidence_fts) AS rank "
                "FROM evidence_fts JOIN evidence e ON e.id = evidence_fts.rowid "
                "WHERE evidence_fts MATCH ? AND e.project_id = ? ORDER BY rank LIMIT ?",
                (match, project_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def cache_get(self, key: str, max_age: float, error_max_age: float) -> tuple[str, Any] | None:
        """Return a fresh cached (status, payload) pair or None."""
        with self.connect() as conn:
            row = conn.execute("SELECT status, payload, fetched_at FROM api_cache WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        age = time.time() - row["fetched_at"]
        limit = max_age if row["status"] == "ok" else error_max_age
        if age > limit:
            return None
        return row["status"], json.loads(row["payload"])

    def cache_put(self, key: str, source: str, query: str, status: str, payload: Any) -> None:
        """Store a collector response."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO api_cache(key, source, query, status, payload, fetched_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET status = excluded.status, payload = excluded.payload, "
                "fetched_at = excluded.fetched_at",
                (key, source, query, status, json.dumps(payload, ensure_ascii=False), time.time()),
            )

    def replace_problems(self, project_id: int, problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace a project's problem statements and their personas."""
        now = time.time()
        with self.connect() as conn:
            conn.execute("DELETE FROM problems WHERE project_id = ?", (project_id,))
            for position, item in enumerate(problems):
                conn.execute(
                    "INSERT INTO problems(project_id, position, title, description, keyword, quote, quote_source, "
                    "node_ids, evidence_ids, trend, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        project_id,
                        position,
                        item["title"],
                        item.get("description", ""),
                        item["keyword"],
                        item.get("quote"),
                        item.get("quote_source"),
                        json.dumps(item.get("node_ids", [])),
                        json.dumps(item.get("evidence_ids", [])),
                        json.dumps(item["trend"]) if item.get("trend") is not None else None,
                        now,
                    ),
                )
            self.touch_project(conn, project_id)
        return self.list_problems(project_id)

    def list_problems(self, project_id: int) -> list[dict[str, Any]]:
        """Return a project's problem statements in display order."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM problems WHERE project_id = ? ORDER BY position", (project_id,)
            ).fetchall()
        return [self._problem(r) for r in rows]

    def get_problem(self, problem_id: int) -> dict[str, Any] | None:
        """Return one problem statement or None."""
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
        return self._problem(row) if row else None

    def _problem(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["chosen"] = bool(item["chosen"])
        item["node_ids"] = json.loads(item["node_ids"])
        item["evidence_ids"] = json.loads(item["evidence_ids"])
        # Previous versions stored search suggestions as problem quotes and citations.
        if item["quote_source"] == "autocomplete":
            item["quote"] = item["quote_source"] = None
        item["evidence_ids"] = [
            e["id"] for e in self.evidence_by_ids(item["evidence_ids"]) if e["source"] in ("community", "reddit")
        ]
        item["trend"] = json.loads(item["trend"]) if item["trend"] else None
        return item

    def update_problem_trend(self, problem_id: int, trend: dict[str, Any]) -> None:
        """Store refreshed trend data for a problem."""
        with self.connect() as conn:
            conn.execute("UPDATE problems SET trend = ? WHERE id = ?", (json.dumps(trend), problem_id))

    def choose_problem(self, problem_id: int) -> dict[str, Any] | None:
        """Mark one problem as the project's chosen problem."""
        problem = self.get_problem(problem_id)
        if problem is None:
            return None
        with self.connect() as conn:
            conn.execute("UPDATE problems SET chosen = (id = ?) WHERE project_id = ?", (problem_id, problem["project_id"]))
            self.touch_project(conn, problem["project_id"])
        return self.get_problem(problem_id)

    def replace_personas(self, project_id: int, problem_id: int, personas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace the personas generated for a problem."""
        now = time.time()
        with self.connect() as conn:
            conn.execute("DELETE FROM personas WHERE problem_id = ?", (problem_id,))
            for position, item in enumerate(personas):
                conn.execute(
                    "INSERT INTO personas(project_id, problem_id, position, name, age, role, quote, options, evidence_ids, profile, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        project_id,
                        problem_id,
                        position,
                        item["name"],
                        item.get("age"),
                        item.get("role", ""),
                        item.get("quote", ""),
                        json.dumps(item.get("options", []), ensure_ascii=False),
                        json.dumps(item.get("evidence_ids", [])),
                        json.dumps(item.get("profile", {}), ensure_ascii=False),
                        now,
                    ),
                )
        return self.list_personas(problem_id)

    def list_personas(self, problem_id: int) -> list[dict[str, Any]]:
        """Return the personas of a problem in display order."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM personas WHERE problem_id = ? ORDER BY position", (problem_id,)
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["profile"] = json.loads(item["profile"])
            item["options"] = json.loads(item["options"])
            item["evidence_ids"] = json.loads(item["evidence_ids"])
            items.append(item)
        return items

    def choose_persona(self, persona_id: int, option: int) -> dict[str, Any] | None:
        """Select one persona and one of its problems, clearing other selections for the same problem."""
        with self.connect() as conn:
            row = conn.execute("SELECT problem_id, options FROM personas WHERE id = ?", (persona_id,)).fetchone()
            if row is None or not 0 <= option < len(json.loads(row["options"])):
                return None
            conn.execute("UPDATE personas SET chosen_option = NULL WHERE problem_id = ?", (row["problem_id"],))
            conn.execute("UPDATE personas SET chosen_option = ? WHERE id = ?", (option, persona_id))
        return next(p for p in self.list_personas(row["problem_id"]) if p["id"] == persona_id)

    def evidence_for_nodes(self, node_ids: list[int], per_node: int = 6) -> list[dict[str, Any]]:
        """Return the strongest evidence items attached to the given nodes."""
        items: list[dict[str, Any]] = []
        with self.connect() as conn:
            for node_id in node_ids:
                rows = conn.execute(
                    "SELECT id, node_id, source, title, body, url, weight FROM evidence WHERE node_id = ? "
                    "AND source IN ('community', 'reddit', 'autocomplete') ORDER BY source != 'autocomplete' DESC, weight DESC LIMIT ?",
                    (node_id, per_node),
                ).fetchall()
                items.extend(dict(r) for r in rows)
        return items

    def unembedded_evidence(self, project_id: int, model: str) -> list[dict[str, Any]]:
        """Return retrievable evidence of a project that has no vector for the given model yet."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT e.id, e.title, e.body FROM evidence e LEFT JOIN evidence_vectors v "
                "ON v.evidence_id = e.id AND v.model = ? WHERE e.project_id = ? AND v.evidence_id IS NULL "
                "AND e.source IN ('community', 'reddit', 'autocomplete') ORDER BY e.id",
                (model, project_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_evidence_vectors(self, model: str, vectors: list[tuple[int, bytes]]) -> None:
        """Store evidence vectors for one embedding model."""
        with self.connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO evidence_vectors(evidence_id, model, vector) VALUES (?, ?, ?)",
                [(evidence_id, model, blob) for evidence_id, blob in vectors],
            )

    def evidence_vectors(self, project_id: int, model: str) -> list[dict[str, Any]]:
        """Return a project's embedded evidence together with the raw vectors."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT e.id, e.node_id, e.source, e.title, e.body, e.url, e.weight, v.vector FROM evidence e "
                "JOIN evidence_vectors v ON v.evidence_id = e.id AND v.model = ? WHERE e.project_id = ?",
                (model, project_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def query_vector(self, model: str, query: str) -> bytes | None:
        """Return the cached vector of a query text."""
        with self.connect() as conn:
            row = conn.execute("SELECT vector FROM query_vectors WHERE model = ? AND query = ?", (model, query)).fetchone()
        return row["vector"] if row else None

    def save_query_vector(self, model: str, query: str, blob: bytes) -> None:
        """Cache the vector of a query text."""
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO query_vectors(model, query, vector) VALUES (?, ?, ?)", (model, query, blob)
            )

    @staticmethod
    def _feature(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["keywords"] = json.loads(item["keywords"])
        item["evidence_ids"] = json.loads(item["evidence_ids"])
        return item

    def list_features(self, project_id: int) -> list[dict[str, Any]]:
        """Return a project's features ordered by priority column and position."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM features WHERE project_id = ? ORDER BY "
                "CASE priority WHEN 'must' THEN 0 WHEN 'should' THEN 1 WHEN 'could' THEN 2 ELSE 3 END, position, id",
                (project_id,),
            ).fetchall()
        return [self._feature(r) for r in rows]

    def get_feature(self, feature_id: int) -> dict[str, Any] | None:
        """Return one feature or None."""
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM features WHERE id = ?", (feature_id,)).fetchone()
        return self._feature(row) if row else None

    def _insert_feature(self, conn: sqlite3.Connection, project_id: int, item: dict[str, Any], now: float) -> int:
        cur = conn.execute(
            "INSERT INTO features(project_id, priority, position, title, description, keywords, evidence_ids, "
            "support, pool, demand, origin, impact, effort, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                item["priority"],
                item.get("position", 0),
                item["title"],
                item.get("description", ""),
                json.dumps(item.get("keywords", []), ensure_ascii=False),
                json.dumps(item.get("evidence_ids", [])),
                item.get("support", 0),
                item.get("pool", 0),
                item.get("demand", 0),
                item.get("origin", "ai"),
                item.get("impact", 1),
                item.get("effort", 2),
                now,
            ),
        )
        return int(cur.lastrowid)

    def replace_features(self, project_id: int, features: list[dict[str, Any]], keep_user: bool = True) -> list[dict[str, Any]]:
        """Replace AI-proposed features, keeping the ones the user wrote unless told otherwise."""
        now = time.time()
        with self.connect() as conn:
            if keep_user:
                conn.execute("DELETE FROM features WHERE project_id = ? AND origin = 'ai'", (project_id,))
            else:
                conn.execute("DELETE FROM features WHERE project_id = ?", (project_id,))
            for item in features:
                self._insert_feature(conn, project_id, item, now)
            self.touch_project(conn, project_id)
        return self.list_features(project_id)

    def add_feature(self, project_id: int, item: dict[str, Any]) -> dict[str, Any]:
        """Append a feature at the end of its priority column."""
        with self.connect() as conn:
            last = conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM features WHERE project_id = ? AND priority = ?",
                (project_id, item["priority"]),
            ).fetchone()[0]
            feature_id = self._insert_feature(conn, project_id, {**item, "position": last + 1}, time.time())
            self.touch_project(conn, project_id)
        return self.get_feature(feature_id)

    def update_feature(self, feature_id: int, **fields: Any) -> dict[str, Any] | None:
        """Update editable feature fields."""
        allowed = {"priority", "position", "title", "description", "keywords", "evidence_ids", "support", "pool", "demand", "impact", "effort"}
        values = {k: v for k, v in fields.items() if k in allowed and v is not None}
        for key in ("keywords", "evidence_ids"):
            if key in values:
                values[key] = json.dumps(values[key], ensure_ascii=False)
        if values:
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE features SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?",
                    (*values.values(), feature_id),
                )
        return self.get_feature(feature_id)

    def reorder_features(self, project_id: int, order: list[tuple[int, str, int]]) -> list[dict[str, Any]]:
        """Apply (feature id, priority, position) triples from the board."""
        with self.connect() as conn:
            conn.executemany(
                "UPDATE features SET priority = ?, position = ? WHERE id = ? AND project_id = ?",
                [(priority, position, feature_id, project_id) for feature_id, priority, position in order],
            )
            self.touch_project(conn, project_id)
        return self.list_features(project_id)

    def delete_feature(self, feature_id: int) -> None:
        """Delete a feature."""
        with self.connect() as conn:
            conn.execute("DELETE FROM features WHERE id = ?", (feature_id,))

    def get_flow(self, project_id: int) -> dict[str, Any] | None:
        """Return the stored user flow document with its pending AI suggestions."""
        with self.connect() as conn:
            row = conn.execute("SELECT data, suggestions, updated_at FROM flows WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            return None
        return {"flow": json.loads(row["data"]), "suggestions": json.loads(row["suggestions"]), "updated_at": row["updated_at"]}

    def save_flow(self, project_id: int, flow: dict[str, Any], suggestions: list[dict[str, Any]] | None = None) -> None:
        """Store the user flow document, optionally replacing the AI suggestions."""
        now = time.time()
        with self.connect() as conn:
            if suggestions is None:
                conn.execute(
                    "INSERT INTO flows(project_id, data, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(project_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                    (project_id, json.dumps(flow, ensure_ascii=False), now),
                )
            else:
                conn.execute(
                    "INSERT INTO flows(project_id, data, suggestions, updated_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(project_id) DO UPDATE SET data = excluded.data, suggestions = excluded.suggestions, "
                    "updated_at = excluded.updated_at",
                    (project_id, json.dumps(flow, ensure_ascii=False), json.dumps(suggestions, ensure_ascii=False), now),
                )
            self.touch_project(conn, project_id)

    def get_validation(self, project_id: int) -> dict[str, Any] | None:
        """Return the stored validation plan, interviews and verdicts of a project."""
        with self.connect() as conn:
            row = conn.execute("SELECT data FROM validations WHERE project_id = ?", (project_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_validation(self, project_id: int, data: dict[str, Any]) -> None:
        """Store the validation document of a project."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO validations(project_id, data, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                (project_id, json.dumps(data, ensure_ascii=False), time.time()),
            )
            self.touch_project(conn, project_id)

    def chosen_persona(self, project_id: int) -> dict[str, Any] | None:
        """Return the persona picked in Define together with its chosen sub-problem."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT pe.* FROM personas pe JOIN problems pr ON pr.id = pe.problem_id "
                "WHERE pe.project_id = ? AND pr.chosen = 1 AND pe.chosen_option IS NOT NULL LIMIT 1",
                (project_id,),
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["options"] = json.loads(item["options"])
        item["profile"] = json.loads(item["profile"])
        item["focus"] = item["options"][item["chosen_option"]] if item["chosen_option"] < len(item["options"]) else ""
        return item

    def get_document(self, project_id: int, kind: str) -> dict[str, Any] | None:
        """Return a project's JSON document of the given kind (board, empathy or tests)."""
        with self.connect() as conn:
            row = conn.execute("SELECT data FROM documents WHERE project_id = ? AND kind = ?", (project_id, kind)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_document(self, project_id: int, kind: str, data: dict[str, Any]) -> None:
        """Store a project's JSON document of the given kind."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO documents(project_id, kind, data, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(project_id, kind) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                (project_id, kind, json.dumps(data, ensure_ascii=False), time.time()),
            )
            self.touch_project(conn, project_id)
