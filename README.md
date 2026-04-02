# VaultMind / MemoryOS MVP

基于 `/Users/mako/Desktop/memoryos_spec_v_1.md` 落地的 v1 服务端 MVP。

当前实现重点：

- 多 Agent 命名空间隔离：每个 Agent 拥有独立目录、独立 SQLite/FTS、独立队列、独立 active context。
- `candidate -> committed memory` 双阶段写入。
- FastAPI 服务端，默认端口 `8765`。
- Markdown 正文 + SQLite 元数据/FTS + 轻量本地向量召回。
- `lightweight` 与 `agentic` 两种检索模式。
- 用户级 `systemd` 部署脚本与 unit 模板。

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

项目里附带几个常用脚本：

```bash
./scripts/start_api.sh
./scripts/run_worker_once.sh nexus
./scripts/install_user_service.sh
```

推荐宿主机目录：

```text
/opt/memoryos/app
/opt/memoryos/data
/opt/memoryos/logs
```

如需放到服务器：

1. `git clone <repo> ~/VaultMind`
2. `cd ~/VaultMind`
3. `python3 -m pip install --user --break-system-packages -e .`
4. `cp config/memoryos.env.example ~/.config/memoryos.env`
5. `./scripts/install_user_service.sh`
6. `systemctl --user enable --now memoryos-api.service`

## Test

```bash
source .venv/bin/activate
pytest
```

## systemd --user

推荐在支持 `systemd --user` 的宿主机上使用仓库内提供的单元模板：

- [memoryos-api.service](/Users/mako/Lab/VaultMind/deploy/systemd/user/memoryos-api.service)
- [memoryos-worker.service](/Users/mako/Lab/VaultMind/deploy/systemd/user/memoryos-worker.service)
- [memoryos-worker.timer](/Users/mako/Lab/VaultMind/deploy/systemd/user/memoryos-worker.timer)

安装脚本会把这些文件复制到 `~/.config/systemd/user/`，并保留一个 `~/.config/memoryos.env` 环境文件。

常用命令：

```bash
systemctl --user daemon-reload
systemctl --user enable --now memoryos-api.service
systemctl --user enable --now memoryos-worker.timer
systemctl --user status memoryos-api.service
journalctl --user -u memoryos-api.service -n 100 --no-pager
```

## Remote Status

当前 `wisepulse-tailscale` 的实际部署路径：

```text
/home/mako/VaultMind
```

当前服务默认数据目录：

```text
/home/mako/VaultMind/var/data
```
