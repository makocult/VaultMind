from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from memoryos.app import create_app
from memoryos.config import Settings


def _headers(agent: str) -> dict[str, str]:
    key_map = {
        "nexus": "dev-nexus-key",
        "morgan": "dev-morgan-key",
        "anya": "dev-anya-key",
    }
    return {"X-Api-Key": key_map[agent], "X-Agent-Id": agent}


def test_candidate_commit_retrieve_and_isolation(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path / "data")
    client = TestClient(create_app(settings))

    nexus_candidate = {
        "session_id": "tg_20260402_001",
        "text": "Nexus 确认 MemoryOS v1 先服务端后 OpenClaw Skill。",
        "summary": "MemoryOS v1 先服务端后 OpenClaw Skill。",
        "tags": ["项目", "开发顺序"],
        "entities": ["MemoryOS", "OpenClaw", "Nexus"],
    }
    response = client.post("/api/v1/candidate/store", json=nexus_candidate, headers=_headers("nexus"))
    assert response.status_code == 200
    candidate_id = response.json()["id"]

    commit_response = client.post("/api/v1/commit/run-item/" + candidate_id, headers=_headers("nexus"))
    assert commit_response.status_code == 200
    assert commit_response.json()["action"] == "committed"
    memory_id = commit_response.json()["memory_id"]

    retrieve_response = client.post(
        "/api/v1/memory/retrieve",
        json={
            "query": "上次关于 MemoryOS 的开发顺序是怎么定的？",
            "memory_types": ["semantic", "relational"],
            "mode": "lightweight",
            "limit": 5,
            "include_body": True,
            "session_id": "tg_20260402_001",
        },
        headers=_headers("nexus"),
    )
    assert retrieve_response.status_code == 200
    payload = retrieve_response.json()
    assert payload["results"][0]["id"] == memory_id
    assert "服务端后 OpenClaw Skill" in payload["results"][0]["summary"]
    assert "Evidence" in payload["results"][0]["body"]

    client.post(
        "/api/v1/candidate/store",
        json={
            "session_id": "discord_001",
            "text": "Morgan 维护自己的隔离命名空间，不能被 Nexus 看到。",
            "summary": "Morgan 的命名空间应与 Nexus 隔离。",
            "tags": ["隔离"],
            "entities": ["Morgan", "Nexus"],
        },
        headers=_headers("morgan"),
    )
    client.post("/api/v1/commit/run-once", json={"limit": 10}, headers=_headers("morgan"))

    isolated_response = client.post(
        "/api/v1/memory/list",
        json={"limit": 20},
        headers=_headers("nexus"),
    )
    assert isolated_response.status_code == 200
    ids = {item["id"] for item in isolated_response.json()}
    assert memory_id in ids
    assert all("Morgan 的命名空间应与 Nexus 隔离。" != item["summary"] for item in isolated_response.json())
