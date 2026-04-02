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


def test_active_context_auth_and_reset(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path / "data")
    client = TestClient(create_app(settings))

    client.post(
        "/api/v1/candidate/store",
        json={
            "session_id": "ctx_session",
            "text": "Nexus 正在整理 MemoryOS 部署方案。",
            "summary": "Nexus 正在整理部署方案。",
            "tags": ["部署"],
            "entities": ["Nexus", "MemoryOS"],
        },
        headers=_headers("nexus"),
    )
    client.post("/api/v1/commit/run-once", json={"limit": 10}, headers=_headers("nexus"))

    refresh_response = client.post(
        "/api/v1/active-context/refresh",
        json={"session_id": "ctx_session", "current_topic": "deployment"},
        headers=_headers("nexus"),
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["current_topic"] == "deployment"
    assert refresh_response.json()["recent_memory_ids"]

    get_response = client.get(
        "/api/v1/active-context",
        params={"session_id": "ctx_session"},
        headers=_headers("nexus"),
    )
    assert get_response.status_code == 200
    assert get_response.json()["session_id"] == "ctx_session"

    forbidden_response = client.get(
        "/api/v1/active-context",
        params={"session_id": "ctx_session"},
        headers={"X-Api-Key": "dev-nexus-key", "X-Agent-Id": "morgan"},
    )
    assert forbidden_response.status_code == 403

    reset_response = client.post(
        "/api/v1/active-context/reset",
        json={"session_id": "ctx_session"},
        headers=_headers("nexus"),
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["deleted"] is True

    missing_response = client.get(
        "/api/v1/active-context",
        params={"session_id": "ctx_session"},
        headers=_headers("nexus"),
    )
    assert missing_response.status_code == 404


def test_dedup_and_agentic_retrieval(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path / "data")
    client = TestClient(create_app(settings))

    first = client.post(
        "/api/v1/candidate/store",
        json={
            "session_id": "agentic_001",
            "text": "MemoryOS 改成先服务端后 Skill，因为这样更容易调试和回滚。",
            "summary": "MemoryOS 先服务端后 Skill，理由是调试和回滚更容易。",
            "tags": ["原则", "顺序"],
            "entities": ["MemoryOS", "Skill"],
            "memory_type_hint": "relational",
            "metadata": {"relation": "decision_reason"},
        },
        headers=_headers("nexus"),
    )
    second = client.post(
        "/api/v1/candidate/store",
        json={
            "session_id": "agentic_001",
            "text": "MemoryOS 改成先服务端后 Skill，因为这样更容易调试和回滚。",
            "summary": "MemoryOS 先服务端后 Skill，理由是调试和回滚更容易。",
            "tags": ["原则", "顺序"],
            "entities": ["MemoryOS", "Skill"],
            "memory_type_hint": "relational",
            "metadata": {"relation": "decision_reason"},
        },
        headers=_headers("nexus"),
    )
    assert first.status_code == 200
    assert second.status_code == 200

    first_commit = client.post(
        "/api/v1/commit/run-item/" + first.json()["id"],
        headers=_headers("nexus"),
    )
    second_commit = client.post(
        "/api/v1/commit/run-item/" + second.json()["id"],
        headers=_headers("nexus"),
    )
    assert first_commit.status_code == 200
    assert second_commit.status_code == 200
    assert first_commit.json()["action"] == "committed"
    assert second_commit.json()["action"] == "deduped"
    assert second_commit.json()["memory_id"] == first_commit.json()["memory_id"]

    retrieve_response = client.post(
        "/api/v1/memory/retrieve",
        json={
            "query": "为什么 MemoryOS 要先做服务端？",
            "mode": "agentic",
            "limit": 3,
            "include_body": True,
            "session_id": "agentic_001",
        },
        headers=_headers("nexus"),
    )
    assert retrieve_response.status_code == 200
    payload = retrieve_response.json()
    assert payload["mode"] == "agentic"
    assert payload["rounds"] >= 1
    assert payload["results"]
    assert "调试和回滚" in payload["results"][0]["body"]


def test_direct_memory_create_patch_and_delete(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path / "data")
    client = TestClient(create_app(settings))

    create_response = client.post(
        "/api/v1/memory/create",
        json={
            "session_id": "hermes_memory_session",
            "memory_type": "semantic",
            "source_type": "hermes-memory-tool",
            "source_ref": "hermes://memory/memory",
            "summary": "Hermes should keep replies concise.",
            "body": "Hermes should keep replies concise.",
            "tags": ["hermes", "hermes-memory", "hermes-target:memory"],
            "entities": ["Hermes"],
            "stability": "high",
            "importance": 0.85,
            "confidence": 0.9,
        },
        headers=_headers("nexus"),
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["summary"] == "Hermes should keep replies concise."
    assert created["body"] == "Hermes should keep replies concise."
    assert "hermes-memory" in created["tags"]

    memory_id = created["id"]
    list_response = client.post(
        "/api/v1/memory/list",
        json={"limit": 10, "tags": ["hermes-memory"]},
        headers=_headers("nexus"),
    )
    assert list_response.status_code == 200
    assert any(item["id"] == memory_id for item in list_response.json())

    patch_response = client.patch(
        f"/api/v1/memory/{memory_id}",
        json={
            "summary": "Hermes should keep replies very concise.",
            "body": "Hermes should keep replies very concise.",
            "tags": ["hermes", "hermes-memory", "hermes-target:memory", "updated"],
        },
        headers=_headers("nexus"),
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["summary"] == "Hermes should keep replies very concise."
    assert patched["body"] == "Hermes should keep replies very concise."
    assert "updated" in patched["tags"]

    delete_response = client.delete(f"/api/v1/memory/{memory_id}", headers=_headers("nexus"))
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    missing_response = client.get(f"/api/v1/memory/{memory_id}", headers=_headers("nexus"))
    assert missing_response.status_code == 404
