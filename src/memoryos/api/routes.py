from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from memoryos.api.deps import AgentContext, get_runtime, require_agent
from memoryos.models.schemas import (
    ActiveContextRecord,
    ActiveContextRefreshRequest,
    CandidateBatchStoreRequest,
    CandidateRecord,
    CandidateStoreRequest,
    CommitRunRequest,
    CommitRunResponse,
    MemoryListRequest,
    MemoryPatchRequest,
    MemoryRecord,
    MemoryRetrieveRequest,
    MemoryRetrieveResponse,
    SessionRequest,
)
from memoryos.services.commit import CommitService
from memoryos.services.retrieval import RetrievalService
from memoryos.services.router import MemoryRouter


router = APIRouter(prefix="/api/v1")


def _store_for(request: Request, agent_context: AgentContext):
    return get_runtime(request).store_for(agent_context.agent)


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> dict[str, object]:
    runtime = get_runtime(request)
    return {
        "status": "ready",
        "agents": runtime.settings.agents,
        "data_root": str(runtime.settings.data_root),
    }


@router.post("/candidate/store", response_model=CandidateRecord)
def store_candidate(
    payload: CandidateStoreRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> CandidateRecord:
    return _store_for(request, agent_context).store_candidate(payload)


@router.post("/candidate/batch-store", response_model=list[CandidateRecord])
def batch_store_candidate(
    payload: CandidateBatchStoreRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> list[CandidateRecord]:
    store = _store_for(request, agent_context)
    return [store.store_candidate(item) for item in payload.items]


@router.get("/candidate/list", response_model=list[CandidateRecord])
def list_candidates(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    agent_context: AgentContext = Depends(require_agent),
) -> list[CandidateRecord]:
    return _store_for(request, agent_context).list_candidates(limit=limit, status=status_filter)


@router.post("/commit/run-once", response_model=CommitRunResponse)
def commit_run_once(
    payload: CommitRunRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> CommitRunResponse:
    service = CommitService()
    return service.run_once(_store_for(request, agent_context), payload.limit)


@router.post("/commit/run-item/{candidate_id}")
def commit_run_item(
    candidate_id: str,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> dict[str, object]:
    service = CommitService()
    result = service.run_item(_store_for(request, agent_context), candidate_id)
    return result.model_dump()


@router.post("/commit/reindex")
def commit_reindex(
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> dict[str, object]:
    rebuilt = _store_for(request, agent_context).rebuild_indexes()
    return {"agent": agent_context.agent, "rebuilt": rebuilt}


@router.post("/memory/retrieve", response_model=MemoryRetrieveResponse)
def memory_retrieve(
    payload: MemoryRetrieveRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> MemoryRetrieveResponse:
    runtime = get_runtime(request)
    retriever = RetrievalService(MemoryRouter(runtime.settings))
    return retriever.retrieve(store=runtime.store_for(agent_context.agent), request=payload)


@router.get("/memory/{memory_id}", response_model=MemoryRecord)
def get_memory(
    memory_id: str,
    request: Request,
    include_body: bool = Query(default=True),
    agent_context: AgentContext = Depends(require_agent),
) -> MemoryRecord:
    memory = _store_for(request, agent_context).get_memory(memory_id, include_body=include_body)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory not found")
    return memory


@router.post("/memory/list", response_model=list[MemoryRecord])
def list_memories(
    payload: MemoryListRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> list[MemoryRecord]:
    return _store_for(request, agent_context).list_memories(
        limit=payload.limit,
        memory_types=payload.memory_types,
        tags=payload.tags,
        entities=payload.entities,
        query=payload.query,
    )


@router.patch("/memory/{memory_id}", response_model=MemoryRecord)
def patch_memory(
    memory_id: str,
    payload: MemoryPatchRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> MemoryRecord:
    memory = _store_for(request, agent_context).update_memory(memory_id, payload)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory not found")
    return memory


@router.delete("/memory/{memory_id}")
def delete_memory(
    memory_id: str,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> dict[str, object]:
    deleted = _store_for(request, agent_context).delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory not found")
    return {"deleted": True, "memory_id": memory_id}


@router.get("/active-context", response_model=ActiveContextRecord)
def get_active_context(
    request: Request,
    session_id: str = Query(...),
    agent_context: AgentContext = Depends(require_agent),
) -> ActiveContextRecord:
    context = _store_for(request, agent_context).get_active_context(session_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="active context not found")
    return context


@router.post("/active-context/refresh", response_model=ActiveContextRecord)
def refresh_active_context(
    payload: ActiveContextRefreshRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> ActiveContextRecord:
    store = _store_for(request, agent_context)
    recent_memory_ids = payload.recent_memory_ids
    topic_entities = payload.topic_entities
    if not recent_memory_ids:
        recent_memories = store.recent_memories(limit=5)
        recent_memory_ids = [memory.id for memory in recent_memories]
        if not topic_entities:
            topic_entities = list(dict.fromkeys(entity for memory in recent_memories for entity in memory.entities))[:6]
    return store.set_active_context(
        session_id=payload.session_id,
        current_topic=payload.current_topic or "general",
        recent_memory_ids=recent_memory_ids,
        topic_entities=topic_entities,
        weights=payload.weights,
    )


@router.post("/active-context/reset")
def reset_active_context(
    payload: SessionRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> dict[str, object]:
    deleted = _store_for(request, agent_context).reset_active_context(payload.session_id)
    return {"deleted": deleted, "session_id": payload.session_id}


@router.post("/maintenance/flush-queue", response_model=CommitRunResponse)
def maintenance_flush_queue(
    payload: CommitRunRequest,
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> CommitRunResponse:
    return CommitService().run_once(_store_for(request, agent_context), payload.limit)


@router.post("/maintenance/rebuild-index")
def maintenance_rebuild_index(
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> dict[str, object]:
    rebuilt = _store_for(request, agent_context).rebuild_indexes()
    return {"rebuilt": rebuilt, "agent": agent_context.agent}


@router.get("/maintenance/stats")
def maintenance_stats(
    request: Request,
    agent_context: AgentContext = Depends(require_agent),
) -> dict[str, object]:
    return _store_for(request, agent_context).stats()
