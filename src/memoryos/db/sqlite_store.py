from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from memoryos.config import Settings
from memoryos.core.ids import new_candidate_id, new_memory_id
from memoryos.core.text import (
    make_hash_vector,
    make_summary,
    normalize_text,
    strip_front_matter,
    tokenize,
)
from memoryos.core.time import now_iso
from memoryos.models.schemas import (
    ActiveContextRecord,
    ActiveContextWeights,
    CandidateRecord,
    CandidateStoreRequest,
    MemoryPatchRequest,
    MemoryRecord,
)


class AgentStore:
    def __init__(self, settings: Settings, agent: str):
        self.settings = settings
        self.agent = agent
        self.root = settings.data_root / agent
        self.semantic_dir = self.root / "semantic"
        self.relational_dir = self.root / "relational"
        self.opinion_dir = self.root / "opinion"
        self.queue_dir = self.root / "queue"
        self.active_dir = self.root / "active"
        self.tmp_dir = self.root / "tmp"
        self.index_dir = self.root / "index"
        self.db_path = self.index_dir / "metadata.sqlite"

    def bootstrap(self) -> None:
        for path in [
            self.semantic_dir,
            self.relational_dir,
            self.opinion_dir,
            self.queue_dir,
            self.active_dir,
            self.tmp_dir,
            self.index_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    event_timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    importance REAL NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_score REAL NOT NULL,
                    recency_score REAL NOT NULL,
                    consistency_score REAL NOT NULL,
                    source_count INTEGER NOT NULL,
                    stability TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    related_ids_json TEXT NOT NULL,
                    supersedes_json TEXT NOT NULL,
                    contradicts_json TEXT NOT NULL,
                    merged_from_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    body_path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    event_timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_path TEXT NOT NULL,
                    memory_type_hint TEXT,
                    summary TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    linked_memory_id TEXT,
                    processing_note TEXT
                );
                CREATE TABLE IF NOT EXISTS relation_edges (
                    edge_id TEXT PRIMARY KEY,
                    src_entity TEXT NOT NULL,
                    dst_entity TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    event_timestamp TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    weight REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_contexts (
                    session_id TEXT PRIMARY KEY,
                    current_topic TEXT NOT NULL,
                    recent_memory_ids_json TEXT NOT NULL,
                    topic_entities_json TEXT NOT NULL,
                    weights_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    memory_id TEXT PRIMARY KEY,
                    vector_json TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    id UNINDEXED,
                    summary,
                    body,
                    tags,
                    entities,
                    tokenize = 'unicode61'
                );
                """
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _loads(self, value: str | None, default: Any) -> Any:
        if not value:
            return default
        return json.loads(value)

    def store_candidate(self, payload: CandidateStoreRequest) -> CandidateRecord:
        candidate_id = new_candidate_id()
        timestamp = payload.timestamp or now_iso()
        created_at = now_iso()
        summary = payload.summary or make_summary(payload.text)
        record = CandidateRecord(
            id=candidate_id,
            status="pending",
            session_id=payload.session_id,
            source_type=payload.source_type,
            source_ref=payload.source_ref,
            timestamp=timestamp,
            created_at=created_at,
            updated_at=created_at,
            memory_type_hint=payload.memory_type_hint,
            summary=summary,
            text=payload.text,
            tags=payload.tags,
            entities=payload.entities,
            metadata=payload.metadata,
        )
        payload_path = self.queue_dir / f"{candidate_id}.json"
        payload_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO candidates (
                    id, status, session_id, source_type, source_ref, event_timestamp,
                    created_at, updated_at, payload_path, memory_type_hint, summary,
                    raw_text, tags_json, entities_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.status,
                    record.session_id,
                    record.source_type,
                    record.source_ref,
                    record.timestamp,
                    record.created_at,
                    record.updated_at,
                    str(payload_path),
                    record.memory_type_hint,
                    record.summary,
                    record.text,
                    self._json(record.tags),
                    self._json(record.entities),
                    self._json(record.metadata),
                ),
            )
            conn.commit()
        return record

    def list_candidates(self, limit: int = 50, status: str | None = None) -> list[CandidateRecord]:
        query = "SELECT * FROM candidates"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._candidate_from_row(row) for row in rows]

    def get_candidate(self, candidate_id: str) -> CandidateRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            return None
        return self._candidate_from_row(row)

    def list_pending_candidates(self, limit: int) -> list[CandidateRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._candidate_from_row(row) for row in rows]

    def update_candidate_status(
        self,
        candidate_id: str,
        status: str,
        linked_memory_id: str | None = None,
        processing_note: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE candidates
                SET status = ?, linked_memory_id = ?, processing_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, linked_memory_id, processing_note, now_iso(), candidate_id),
            )
            conn.commit()

    def create_memory(self, memory: MemoryRecord, body_markdown: str, edges: list[dict[str, Any]] | None = None) -> None:
        memory_dir = {
            "semantic": self.semantic_dir,
            "relational": self.relational_dir,
            "opinion": self.opinion_dir,
        }[memory.memory_type]
        body_path = memory_dir / f"{memory.id}.md"
        front_matter = {
            "id": memory.id,
            "agent": memory.agent,
            "memory_type": memory.memory_type,
            "status": memory.status,
            "session_id": memory.session_id,
            "source_type": memory.source_type,
            "source_ref": memory.source_ref,
            "timestamp": memory.timestamp,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "importance": memory.importance,
            "confidence": memory.confidence,
            "stability": memory.stability,
            "tags": memory.tags,
            "entities": memory.entities,
            "related_ids": memory.related_ids,
            "supersedes": memory.supersedes,
            "contradicts": memory.contradicts,
            "merged_from": memory.merged_from,
            "summary": memory.summary,
        }
        markdown = "---\n" + yaml.safe_dump(front_matter, allow_unicode=True, sort_keys=False) + "---\n\n" + body_markdown.strip() + "\n"
        body_path.write_text(markdown, encoding="utf-8")
        vector = make_hash_vector(memory.summary)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                    id, agent, memory_type, status, session_id, source_type, source_ref,
                    event_timestamp, created_at, updated_at, importance, confidence,
                    evidence_score, recency_score, consistency_score, source_count,
                    stability, tags_json, entities_json, related_ids_json,
                    supersedes_json, contradicts_json, merged_from_json, summary, body_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.agent,
                    memory.memory_type,
                    memory.status,
                    memory.session_id,
                    memory.source_type,
                    memory.source_ref,
                    memory.timestamp,
                    memory.created_at,
                    memory.updated_at,
                    memory.importance,
                    memory.confidence,
                    memory.evidence_score,
                    memory.recency_score,
                    memory.consistency_score,
                    memory.source_count,
                    memory.stability,
                    self._json(memory.tags),
                    self._json(memory.entities),
                    self._json(memory.related_ids),
                    self._json(memory.supersedes),
                    self._json(memory.contradicts),
                    self._json(memory.merged_from),
                    memory.summary,
                    str(body_path),
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (memory_id, vector_json) VALUES (?, ?)",
                (memory.id, self._json(vector)),
            )
            conn.execute(
                "INSERT INTO memories_fts (id, summary, body, tags, entities) VALUES (?, ?, ?, ?, ?)",
                (
                    memory.id,
                    self._fts_text(memory.summary),
                    self._fts_text(strip_front_matter(markdown)),
                    self._fts_text(" ".join(memory.tags)),
                    self._fts_text(" ".join(memory.entities)),
                ),
            )
            for edge in edges or []:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO relation_edges (
                        edge_id, src_entity, dst_entity, relation, event_timestamp,
                        evidence_ids_json, weight
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge["edge_id"],
                        edge["src_entity"],
                        edge["dst_entity"],
                        edge["relation"],
                        edge["event_timestamp"],
                        self._json(edge["evidence_ids"]),
                        edge["weight"],
                    ),
                )
            conn.commit()

    def get_memory(self, memory_id: str, include_body: bool = True) -> MemoryRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if not row:
            return None
        return self._memory_from_row(row, include_body=include_body)

    def list_memories(
        self,
        limit: int = 20,
        memory_types: list[str] | None = None,
        tags: list[str] | None = None,
        entities: list[str] | None = None,
        query: str | None = None,
    ) -> list[MemoryRecord]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM memories ORDER BY event_timestamp DESC LIMIT 500").fetchall()
        memories = [self._memory_from_row(row, include_body=False) for row in rows]
        filtered = [
            memory
            for memory in memories
            if self._memory_matches(memory, memory_types or [], tags or [], entities or [], query)
        ]
        return filtered[:limit]

    def update_memory(self, memory_id: str, patch: MemoryPatchRequest) -> MemoryRecord | None:
        current = self.get_memory(memory_id, include_body=True)
        if not current:
            return None
        updated = current.model_copy(
            update={
                key: value
                for key, value in patch.model_dump(exclude_none=True).items()
                if key != "body"
            }
        )
        updated.updated_at = now_iso()
        body = patch.body if patch.body is not None else (current.body or "")
        self.delete_memory(memory_id)
        self.create_memory(updated, body_markdown=body)
        return self.get_memory(memory_id, include_body=True)

    def delete_memory(self, memory_id: str) -> bool:
        memory = self.get_memory(memory_id, include_body=False)
        if not memory:
            return False
        body_path = Path(memory.body_path)
        if body_path.exists():
            body_path.unlink()
        with self._conn() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.execute("DELETE FROM embeddings WHERE memory_id = ?", (memory_id,))
            conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            conn.commit()
        return True

    def rebuild_indexes(self) -> int:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM memories").fetchall()
            conn.execute("DELETE FROM memories_fts")
            conn.execute("DELETE FROM embeddings")
            for row in rows:
                memory = self._memory_from_row(row, include_body=True)
                conn.execute(
                    "INSERT INTO memories_fts (id, summary, body, tags, entities) VALUES (?, ?, ?, ?, ?)",
                    (
                        memory.id,
                        self._fts_text(memory.summary),
                        self._fts_text(memory.body or ""),
                        self._fts_text(" ".join(memory.tags)),
                        self._fts_text(" ".join(memory.entities)),
                    ),
                )
                conn.execute(
                    "INSERT INTO embeddings (memory_id, vector_json) VALUES (?, ?)",
                    (memory.id, self._json(make_hash_vector(memory.summary))),
                )
            conn.commit()
        return len(rows)

    def search_fts(self, query: str, memory_types: list[str], limit: int) -> list[MemoryRecord]:
        tokens = tokenize(query)
        if not tokens:
            return self.list_memories(limit=limit, memory_types=memory_types)
        match_query = " OR ".join(tokens)
        placeholders = ",".join("?" for _ in memory_types) if memory_types else ""
        sql = """
            SELECT m.*
            FROM memories_fts f
            JOIN memories m ON m.id = f.id
            WHERE f.memories_fts MATCH ?
        """
        params: list[Any] = [match_query]
        if memory_types:
            sql += f" AND m.memory_type IN ({placeholders})"
            params.extend(memory_types)
        sql += " ORDER BY bm25(memories_fts) LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._memory_from_row(row, include_body=False) for row in rows]

    def search_vector(self, query: str, memory_types: list[str], limit: int) -> list[tuple[MemoryRecord, float]]:
        query_vector = make_hash_vector(query)
        with self._conn() as conn:
            sql = "SELECT m.*, e.vector_json FROM memories m JOIN embeddings e ON m.id = e.memory_id"
            params: list[Any] = []
            if memory_types:
                placeholders = ",".join("?" for _ in memory_types)
                sql += f" WHERE m.memory_type IN ({placeholders})"
                params.extend(memory_types)
            rows = conn.execute(sql, params).fetchall()
        scored: list[tuple[MemoryRecord, float]] = []
        for row in rows:
            vector = self._loads(row["vector_json"], [])
            score = sum(a * b for a, b in zip(query_vector, vector))
            if score > 0:
                scored.append((self._memory_from_row(row, include_body=False), score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def recent_memories(self, limit: int = 5) -> list[MemoryRecord]:
        return self.list_memories(limit=limit)

    def set_active_context(
        self,
        session_id: str,
        current_topic: str,
        recent_memory_ids: list[str],
        topic_entities: list[str],
        weights: ActiveContextWeights,
    ) -> ActiveContextRecord:
        record = ActiveContextRecord(
            session_id=session_id,
            agent=self.agent,
            current_topic=current_topic,
            recent_memory_ids=recent_memory_ids,
            topic_entities=topic_entities,
            weights=weights,
            updated_at=now_iso(),
        )
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO active_contexts (
                    session_id, current_topic, recent_memory_ids_json,
                    topic_entities_json, weights_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    current_topic = excluded.current_topic,
                    recent_memory_ids_json = excluded.recent_memory_ids_json,
                    topic_entities_json = excluded.topic_entities_json,
                    weights_json = excluded.weights_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.session_id,
                    record.current_topic,
                    self._json(record.recent_memory_ids),
                    self._json(record.topic_entities),
                    self._json(record.weights.model_dump()),
                    record.updated_at,
                ),
            )
            conn.commit()
        context_path = self.active_dir / f"{session_id}.json"
        context_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return record

    def get_active_context(self, session_id: str) -> ActiveContextRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_contexts WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return ActiveContextRecord(
            session_id=row["session_id"],
            agent=self.agent,
            current_topic=row["current_topic"],
            recent_memory_ids=self._loads(row["recent_memory_ids_json"], []),
            topic_entities=self._loads(row["topic_entities_json"], []),
            weights=ActiveContextWeights(**self._loads(row["weights_json"], {})),
            updated_at=row["updated_at"],
        )

    def reset_active_context(self, session_id: str) -> bool:
        with self._conn() as conn:
            deleted = conn.execute(
                "DELETE FROM active_contexts WHERE session_id = ?",
                (session_id,),
            ).rowcount
            conn.commit()
        context_path = self.active_dir / f"{session_id}.json"
        if context_path.exists():
            context_path.unlink()
        return bool(deleted)

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            memory_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            candidate_count = conn.execute(
                "SELECT COUNT(*) FROM candidates WHERE status = 'pending'"
            ).fetchone()[0]
            relational_count = conn.execute("SELECT COUNT(*) FROM relation_edges").fetchone()[0]
            active_context_count = conn.execute("SELECT COUNT(*) FROM active_contexts").fetchone()[0]
        return {
            "agent": self.agent,
            "pending_candidates": candidate_count,
            "committed_memories": memory_count,
            "relation_edges": relational_count,
            "active_contexts": active_context_count,
            "db_path": str(self.db_path),
            "queue_dir": str(self.queue_dir),
        }

    def memory_exists(self, memory_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return bool(row)

    def new_memory_template(
        self,
        *,
        memory_type: str,
        session_id: str,
        source_type: str,
        source_ref: str | None,
        timestamp: str,
        summary: str,
        tags: list[str],
        entities: list[str],
    ) -> MemoryRecord:
        memory_id = new_memory_id()
        created_at = now_iso()
        return MemoryRecord(
            id=memory_id,
            agent=self.agent,
            memory_type=memory_type,
            status="committed",
            session_id=session_id,
            source_type=source_type,
            source_ref=source_ref,
            timestamp=timestamp,
            created_at=created_at,
            updated_at=created_at,
            importance=0.5,
            confidence=0.5,
            evidence_score=0.5,
            recency_score=1.0,
            consistency_score=0.7,
            source_count=1,
            stability="medium",
            tags=tags,
            entities=entities,
            related_ids=[],
            supersedes=[],
            contradicts=[],
            merged_from=[],
            summary=summary,
            body_path="",
        )

    def _candidate_from_row(self, row: sqlite3.Row) -> CandidateRecord:
        return CandidateRecord(
            id=row["id"],
            status=row["status"],
            session_id=row["session_id"],
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            timestamp=row["event_timestamp"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            memory_type_hint=row["memory_type_hint"],
            summary=row["summary"],
            text=row["raw_text"],
            tags=self._loads(row["tags_json"], []),
            entities=self._loads(row["entities_json"], []),
            metadata=self._loads(row["metadata_json"], {}),
            linked_memory_id=row["linked_memory_id"],
            processing_note=row["processing_note"],
        )

    def _memory_from_row(self, row: sqlite3.Row, include_body: bool) -> MemoryRecord:
        body = None
        if include_body:
            markdown = Path(row["body_path"]).read_text(encoding="utf-8")
            body = strip_front_matter(markdown)
        return MemoryRecord(
            id=row["id"],
            agent=row["agent"],
            memory_type=row["memory_type"],
            status=row["status"],
            session_id=row["session_id"],
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            timestamp=row["event_timestamp"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            importance=row["importance"],
            confidence=row["confidence"],
            evidence_score=row["evidence_score"],
            recency_score=row["recency_score"],
            consistency_score=row["consistency_score"],
            source_count=row["source_count"],
            stability=row["stability"],
            tags=self._loads(row["tags_json"], []),
            entities=self._loads(row["entities_json"], []),
            related_ids=self._loads(row["related_ids_json"], []),
            supersedes=self._loads(row["supersedes_json"], []),
            contradicts=self._loads(row["contradicts_json"], []),
            merged_from=self._loads(row["merged_from_json"], []),
            summary=row["summary"],
            body_path=row["body_path"],
            body=body,
        )

    def _memory_matches(
        self,
        memory: MemoryRecord,
        memory_types: list[str],
        tags: list[str],
        entities: list[str],
        query: str | None,
    ) -> bool:
        if memory_types and memory.memory_type not in memory_types:
            return False
        if tags and not set(tags).intersection(memory.tags):
            return False
        if entities and not set(entities).intersection(memory.entities):
            return False
        if query:
            haystack = normalize_text(" ".join([memory.summary, " ".join(memory.tags), " ".join(memory.entities)]))
            for token in tokenize(query):
                if token not in haystack.lower():
                    return False
        return True

    def _fts_text(self, text: str) -> str:
        normalized = normalize_text(text)
        tokens = tokenize(normalized)
        token_text = " ".join(tokens)
        return " ".join(part for part in [normalized, token_text] if part).strip()
