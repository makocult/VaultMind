from __future__ import annotations

from typing import Any

from memoryos.core.ids import new_relation_id
from memoryos.core.text import cosine_similarity, make_hash_vector, make_summary, normalize_text
from memoryos.db.sqlite_store import AgentStore
from memoryos.models.schemas import CandidateRecord, CommitItemResult, CommitRunResponse


class CommitService:
    def run_once(self, store: AgentStore, limit: int) -> CommitRunResponse:
        items: list[CommitItemResult] = []
        committed = 0
        deduped = 0
        failed = 0
        for candidate in store.list_pending_candidates(limit):
            try:
                item = self._process_candidate(store, candidate)
            except Exception as exc:  # pragma: no cover - defensive path
                store.update_candidate_status(candidate.id, "failed", processing_note=str(exc))
                item = CommitItemResult(candidate_id=candidate.id, action="failed", note=str(exc))
            if item.action == "committed":
                committed += 1
            elif item.action == "deduped":
                deduped += 1
            elif item.action == "failed":
                failed += 1
            items.append(item)
        return CommitRunResponse(
            agent=store.agent,
            processed=len(items),
            committed=committed,
            deduped=deduped,
            failed=failed,
            items=items,
        )

    def run_item(self, store: AgentStore, candidate_id: str) -> CommitItemResult:
        candidate = store.get_candidate(candidate_id)
        if not candidate:
            return CommitItemResult(candidate_id=candidate_id, action="failed", note="candidate not found")
        if candidate.status != "pending":
            return CommitItemResult(
                candidate_id=candidate_id,
                action="skipped",
                memory_id=candidate.linked_memory_id,
                note=f"candidate already {candidate.status}",
            )
        return self._process_candidate(store, candidate)

    def _process_candidate(self, store: AgentStore, candidate: CandidateRecord) -> CommitItemResult:
        memory_type = self._classify(candidate)
        duplicate_id = self._find_duplicate(store, candidate.summary, [memory_type, "semantic"])
        if duplicate_id:
            store.update_candidate_status(
                candidate.id,
                "deduped",
                linked_memory_id=duplicate_id,
                processing_note="merged into existing memory by similarity",
            )
            return CommitItemResult(
                candidate_id=candidate.id,
                action="deduped",
                memory_id=duplicate_id,
                memory_type=memory_type,
                note="duplicate summary/body",
            )

        summary = make_summary(candidate.summary or candidate.text)
        memory = store.new_memory_template(
            memory_type=memory_type,
            session_id=candidate.session_id,
            source_type=candidate.source_type,
            source_ref=candidate.source_ref,
            timestamp=candidate.timestamp,
            summary=summary,
            tags=candidate.tags,
            entities=candidate.entities,
        )
        memory.importance = self._score_importance(candidate)
        memory.confidence = self._score_confidence(candidate)
        memory.evidence_score = self._score_evidence(candidate)
        memory.recency_score = 1.0
        memory.consistency_score = 0.72
        memory.stability = "low" if memory_type == "opinion" else "medium"
        memory.related_ids = candidate.metadata.get("related_ids", [])
        memory.supersedes = candidate.metadata.get("supersedes", [])
        memory.contradicts = candidate.metadata.get("contradicts", [])
        memory.merged_from = candidate.metadata.get("merged_from", [])

        body_markdown = self._build_body_markdown(candidate)
        edges = self._build_edges(candidate, memory.id, memory_type)
        store.create_memory(memory, body_markdown=body_markdown, edges=edges)
        store.update_candidate_status(candidate.id, "committed", linked_memory_id=memory.id, processing_note="committed")
        return CommitItemResult(
            candidate_id=candidate.id,
            action="committed",
            memory_id=memory.id,
            memory_type=memory_type,
            note="stored as committed memory",
        )

    def _classify(self, candidate: CandidateRecord) -> str:
        if candidate.memory_type_hint:
            return candidate.memory_type_hint
        lowered = normalize_text(candidate.text).lower()
        if any(keyword in lowered for keyword in ["喜欢", "偏好", "倾向", "风格", "prefer", "opinion"]):
            return "opinion"
        if any(keyword in lowered for keyword in ["因为", "导致", "关系", "timeline", "决策", "之前", "昨天", "原因"]):
            return "relational"
        return "semantic"

    def _find_duplicate(self, store: AgentStore, summary: str, memory_types: list[str]) -> str | None:
        query_vector = make_hash_vector(summary)
        for memory, _ in store.search_vector(summary, memory_types, limit=10):
            score = cosine_similarity(query_vector, make_hash_vector(memory.summary))
            if score >= 0.95:
                return memory.id
        return None

    def _build_body_markdown(self, candidate: CandidateRecord) -> str:
        evidence_lines = []
        if candidate.source_ref:
            evidence_lines.append(f"- Source: {candidate.source_ref}")
        evidence_lines.append(f"- Session: {candidate.session_id}")
        notes = ["- Candidate extracted through MemoryOS commit pipeline."]
        if candidate.metadata:
            notes.append(f"- Metadata: {candidate.metadata}")
        title = candidate.summary or make_summary(candidate.text)
        return "\n".join(
            [
                f"## {title}",
                "",
                candidate.text.strip(),
                "",
                "### Evidence",
                *evidence_lines,
                "",
                "### Notes",
                *notes,
            ]
        )

    def _build_edges(self, candidate: CandidateRecord, memory_id: str, memory_type: str) -> list[dict[str, Any]]:
        entities = candidate.entities
        if memory_type != "relational" or len(entities) < 2:
            return []
        return [
            {
                "edge_id": new_relation_id(),
                "src_entity": entities[0],
                "dst_entity": entities[1],
                "relation": candidate.metadata.get("relation", "related_to"),
                "event_timestamp": candidate.timestamp,
                "evidence_ids": [memory_id],
                "weight": 0.8,
            }
        ]

    def _score_importance(self, candidate: CandidateRecord) -> float:
        base = 0.45
        base += min(len(candidate.tags) * 0.06, 0.18)
        base += min(len(candidate.entities) * 0.05, 0.15)
        base += min(len(candidate.text) / 1000.0, 0.15)
        return min(round(base, 2), 0.95)

    def _score_confidence(self, candidate: CandidateRecord) -> float:
        base = 0.56
        if candidate.source_ref:
            base += 0.05
        if candidate.summary:
            base += 0.03
        if candidate.entities:
            base += 0.04
        return min(round(base, 2), 0.92)

    def _score_evidence(self, candidate: CandidateRecord) -> float:
        base = 0.55
        base += min(len(candidate.text) / 1200.0, 0.25)
        if candidate.metadata:
            base += 0.05
        return min(round(base, 2), 0.95)
