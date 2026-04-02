from __future__ import annotations

from collections import Counter

from memoryos.core.text import reciprocal_rank_fusion
from memoryos.db.sqlite_store import AgentStore
from memoryos.models.schemas import MemoryRecord, MemoryRetrieveRequest, MemoryRetrieveResponse
from memoryos.services.router import MemoryRouter, RoutePlan


class RetrievalService:
    def __init__(self, router: MemoryRouter):
        self.router = router

    def retrieve(
        self,
        *,
        store: AgentStore,
        request: MemoryRetrieveRequest,
    ) -> MemoryRetrieveResponse:
        active_context = store.get_active_context(request.session_id) if request.session_id else None
        plan = self.router.plan(agent=store.agent, request=request, active_context=active_context)
        results, entities = self._execute_round(store, plan, request)
        state = "sufficient"
        rounds = 1

        if plan.retrieval_mode == "agentic" and self._needs_expansion(request, results):
            expanded_plan = self.router.expand(plan, entities)
            expanded_results, _ = self._execute_round(store, expanded_plan, request)
            merged = {memory.id: memory for memory in [*results, *expanded_results]}
            results = list(merged.values())[: request.limit]
            rounds = 2
            state = "budget_exceeded" if rounds >= plan.interleave_round_limit and len(results) < request.limit else "sufficient"

        return MemoryRetrieveResponse(
            agent=store.agent,
            mode=plan.retrieval_mode,
            state=state,
            rounds=rounds,
            results=self._hydrate_bodies(store, results, request.include_body),
        )

    def _execute_round(
        self,
        store: AgentStore,
        plan: RoutePlan,
        request: MemoryRetrieveRequest,
    ) -> tuple[list[MemoryRecord], list[str]]:
        fts_results = [
            memory
            for memory in store.search_fts(plan.query, plan.memory_types, plan.topk_budget)
            if self._passes_filters(memory, request)
        ]
        vector_results = [
            memory
            for memory, _ in store.search_vector(plan.query, plan.memory_types, plan.topk_budget)
            if self._passes_filters(memory, request)
        ]
        fused = reciprocal_rank_fusion(
            [
                [memory.id for memory in fts_results],
                [memory.id for memory in vector_results],
            ]
        )
        candidate_map = {memory.id: memory for memory in [*fts_results, *vector_results]}
        scored = []
        for memory_id, score in fused.items():
            memory = candidate_map[memory_id]
            enriched_score = score + (memory.importance * 0.15) + (memory.confidence * 0.1)
            if request.entities and set(request.entities).intersection(memory.entities):
                enriched_score += 0.05
            if request.tags and set(request.tags).intersection(memory.tags):
                enriched_score += 0.05
            scored.append((memory, enriched_score))
        scored.sort(key=lambda item: item[1], reverse=True)
        results = [memory for memory, _ in scored[: request.limit]]
        entity_counter = Counter(entity for memory in results for entity in memory.entities)
        return results, [entity for entity, _ in entity_counter.most_common(4)]

    def _passes_filters(self, memory: MemoryRecord, request: MemoryRetrieveRequest) -> bool:
        if request.tags and not set(request.tags).intersection(memory.tags):
            return False
        if request.entities and not set(request.entities).intersection(memory.entities):
            return False
        return True

    def _needs_expansion(self, request: MemoryRetrieveRequest, results: list[MemoryRecord]) -> bool:
        if len(results) < max(2, request.limit // 2):
            return True
        lowered = request.query.lower()
        return any(token in lowered for token in ["为什么", "原因", "compare", "相比", "之前", "关系"])

    def _hydrate_bodies(self, store: AgentStore, results: list[MemoryRecord], include_body: bool) -> list[MemoryRecord]:
        if not include_body:
            return results
        hydrated: list[MemoryRecord] = []
        for memory in results:
            hydrated_memory = store.get_memory(memory.id, include_body=True)
            if hydrated_memory:
                hydrated.append(hydrated_memory)
        return hydrated
