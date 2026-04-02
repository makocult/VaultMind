from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryType = Literal["semantic", "relational", "opinion"]
RetrieveMode = Literal["lightweight", "agentic", "auto"]
RetrieveState = Literal[
    "init",
    "routed",
    "first_retrieval",
    "gap_analysis",
    "expanded_retrieval",
    "sufficient",
    "budget_exceeded",
    "failed",
]


class CandidateStoreRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1)
    source_type: str = "dialogue"
    source_ref: str | None = None
    timestamp: str | None = None
    memory_type_hint: MemoryType | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateBatchStoreRequest(BaseModel):
    items: list[CandidateStoreRequest]


class CandidateRecord(BaseModel):
    id: str
    status: str
    session_id: str
    source_type: str
    source_ref: str | None = None
    timestamp: str
    created_at: str
    updated_at: str
    memory_type_hint: MemoryType | None = None
    summary: str
    text: str
    tags: list[str]
    entities: list[str]
    metadata: dict[str, Any]
    linked_memory_id: str | None = None
    processing_note: str | None = None


class CommitRunRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=500)


class CommitItemResult(BaseModel):
    candidate_id: str
    action: Literal["committed", "deduped", "skipped", "failed"]
    memory_id: str | None = None
    memory_type: MemoryType | None = None
    note: str | None = None


class CommitRunResponse(BaseModel):
    agent: str
    processed: int
    committed: int
    deduped: int
    failed: int
    items: list[CommitItemResult]


class MemoryListRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    memory_types: list[MemoryType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    query: str | None = None


class MemoryPatchRequest(BaseModel):
    memory_type: MemoryType | None = None
    session_id: str | None = None
    source_type: str | None = None
    source_ref: str | None = None
    timestamp: str | None = None
    summary: str | None = None
    body: str | None = None
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    stability: Literal["low", "medium", "high"] | None = None
    tags: list[str] | None = None
    entities: list[str] | None = None
    related_ids: list[str] | None = None


class MemoryCreateRequest(BaseModel):
    session_id: str
    memory_type: MemoryType
    source_type: str = "api"
    source_ref: str | None = None
    timestamp: str | None = None
    summary: str = Field(min_length=1)
    body: str = ""
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recency_score: float = Field(default=1.0, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.7, ge=0.0, le=1.0)
    source_count: int = Field(default=1, ge=1)
    stability: Literal["low", "medium", "high"] = "medium"
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    related_ids: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    merged_from: list[str] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    id: str
    agent: str
    memory_type: MemoryType
    status: str
    session_id: str
    source_type: str
    source_ref: str | None = None
    timestamp: str
    created_at: str
    updated_at: str
    importance: float
    confidence: float
    evidence_score: float
    recency_score: float
    consistency_score: float
    source_count: int
    stability: Literal["low", "medium", "high"]
    tags: list[str]
    entities: list[str]
    related_ids: list[str]
    supersedes: list[str]
    contradicts: list[str]
    merged_from: list[str]
    summary: str
    body_path: str
    body: str | None = None


class MemoryRetrieveRequest(BaseModel):
    query: str
    memory_types: list[MemoryType] = Field(default_factory=list)
    mode: RetrieveMode = "lightweight"
    limit: int = Field(default=8, ge=1, le=20)
    include_body: bool = False
    session_id: str | None = None
    current_topic: str | None = None
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)


class MemoryRetrieveResponse(BaseModel):
    agent: str
    mode: Literal["lightweight", "agentic"]
    state: RetrieveState
    rounds: int
    results: list[MemoryRecord]


class ActiveContextWeights(BaseModel):
    semantic: float = 0.55
    relational: float = 0.30
    opinion: float = 0.15


class ActiveContextRefreshRequest(BaseModel):
    session_id: str
    current_topic: str | None = None
    recent_memory_ids: list[str] = Field(default_factory=list)
    topic_entities: list[str] = Field(default_factory=list)
    weights: ActiveContextWeights = Field(default_factory=ActiveContextWeights)


class SessionRequest(BaseModel):
    session_id: str


class ActiveContextRecord(BaseModel):
    session_id: str
    agent: str
    current_topic: str
    recent_memory_ids: list[str]
    topic_entities: list[str]
    weights: ActiveContextWeights
    updated_at: str
