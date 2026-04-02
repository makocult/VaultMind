# VaultMind / MemoryOS MVP

基于 `/Users/mako/Desktop/memoryos_spec_v_1.md` 落地的 v1 服务端 MVP。

当前实现重点：

- 多 Agent 命名空间隔离：每个 Agent 拥有独立目录、独立 SQLite/FTS、独立队列、独立 active context。
- `candidate -> committed memory` 双阶段写入。
- FastAPI 服务端，默认端口 `8765`。
- Markdown 正文 + SQLite 元数据/FTS + 轻量本地向量召回。
- `lightweight` 与 `agentic` 两种检索模式。

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
memoryos-api
```

默认数据会写到 `./var/data`。如需覆盖：

```bash
export MEMORYOS_DATA_ROOT=/opt/memoryos/data
export MEMORYOS_API_KEYS_JSON='{"nexus":"change-me","morgan":"change-me-2","anya":"change-me-3"}'
memoryos-api
```

## API

主入口：`http://127.0.0.1:8765/api/v1`

认证头：

- `X-Api-Key`
- `X-Agent-Id`

常用接口：

- `GET /healthz`
- `GET /readyz`
- `POST /candidate/store`
- `POST /candidate/batch-store`
- `GET /candidate/list`
- `POST /commit/run-once`
- `POST /commit/run-item/{candidate_id}`
- `POST /commit/reindex`
- `POST /memory/retrieve`
- `GET /memory/{memory_id}`
- `POST /memory/list`
- `PATCH /memory/{memory_id}`
- `DELETE /memory/{memory_id}`
- `GET /active-context`
- `POST /active-context/refresh`
- `POST /active-context/reset`
- `POST /maintenance/flush-queue`
- `POST /maintenance/rebuild-index`
- `GET /maintenance/stats`

## Deployment

项目里附带两个脚本：

```bash
./scripts/start_api.sh
./scripts/run_worker_once.sh nexus
```

推荐宿主机目录：

```text
/opt/memoryos/app
/opt/memoryos/data
/opt/memoryos/logs
```

如需放到服务器：

1. `git clone <repo> /opt/memoryos/app`
2. `cd /opt/memoryos/app`
3. `MEMORYOS_DATA_ROOT=/opt/memoryos/data ./scripts/start_api.sh`

## Test

```bash
source .venv/bin/activate
pytest
```
