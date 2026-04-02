from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from memoryos.config import Settings
from memoryos.core.text import extract_query_entities
from memoryos.models.schemas import ActiveContextRecord, MemoryRetrieveRequest


class RoutePlan(BaseModel):
    agent: str
    query: str
    memory_types: list[str]
    entities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    retrieval_mode: Literal["lightweight", "agentic"]
    topk_budget: int
    interleave_round_limit: int


class MemoryRouter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def plan(
        self,
        *,
        agent: str,
        request: MemoryRetrieveRequest,
        active_context: ActiveContextRecord | None = None,
    ) -> RoutePlan:
        query = request.query.strip()
        requested_mode = request.mode
        auto_agentic = self._looks_agentic(query)
        retrieval_mode: Literal["lightweight", "agentic"] = (
            "agentic" if requested_mode == "agentic" or (requested_mode == "auto" and auto_agentic) else "lightweight"
        )
        memory_types = request.memory_types or self._suggest_memory_types(query, active_context)
        entities = list(dict.fromkeys([*request.entities, *extract_query_entities(query), *(active_context.topic_entities if active_context else [])]))
        return RoutePlan(
            agent=agent,
            query=query,
            memory_types=memory_types,
            entities=entities[:6],
            tags=request.tags,
            retrieval_mode=retrieval_mode,
            topk_budget=max(request.limit * 3, 12),
            interleave_round_limit=self.settings.interleave_round_limit,
        )

    def expand(self, plan: RoutePlan, results_entities: list[str]) -> RoutePlan:
        expanded_types = list(dict.fromkeys([*plan.memory_types, "relational"]))
        expanded_entities = list(dict.fromkeys([*plan.entities, *results_entities]))
        return plan.model_copy(
            update={
                "memory_types": expanded_types,
                "entities": expanded_entities[:8],
                "topk_budget": max(plan.topk_budget, 18),
            }
        )

    def _suggest_memory_types(self, query: str, active_context: ActiveContextRecord | None) -> list[str]:
        lowered = query.lower()
        if any(keyword in lowered for keyword in ["喜欢", "偏好", "风格", "opinion", "preference"]):
            return ["opinion", "semantic"]
        if self._looks_agentic(query):
            return ["semantic", "relational"]
        if active_context and active_context.weights.relational >= 0.4:
            return ["semantic", "relational"]
        return ["semantic"]

    def _looks_agentic(self, query: str) -> bool:
        lowered = query.lower()
        triggers = [
            "为什么",
            "原因",
            "相比",
            "之前",
            "昨天",
            "今天",
            "timeline",
            "because",
            "compare",
            "decision",
            "关系",
            "因果",
        ]
        return any(trigger in lowered for trigger in triggers)
