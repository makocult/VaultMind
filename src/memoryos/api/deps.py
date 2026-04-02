from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, Request, status

from memoryos.core.runtime import MemoryOSRuntime


@dataclass
class AgentContext:
    agent: str


def get_runtime(request: Request) -> MemoryOSRuntime:
    return request.app.state.runtime


def require_agent(
    request: Request,
    x_api_key: str = Header(..., alias="X-Api-Key"),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
) -> AgentContext:
    runtime = get_runtime(request)
    agent = runtime.settings.agent_for_api_key(x_api_key)
    if not agent:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")
    if x_agent_id and x_agent_id != agent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="agent/key mismatch")
    return AgentContext(agent=agent)
