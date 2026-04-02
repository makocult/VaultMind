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
- `POST /memory/create`
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
./scripts/install_agent_access_env.sh
./scripts/check_memoryos_access.sh
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

## Agent Access

对运行在 `wisepulse` 同一台机器上的 Agent，推荐永远优先使用：

```text
http://127.0.0.1:8765
```

这样可以绕开代理、ACL 和外网路由变量，稳定性最高。

对不在同机、但在同一 Tailscale tailnet 内的 Agent，使用：

```text
http://100.93.59.21:8765
```

并确保设置：

```bash
export NO_PROXY=127.0.0.1,localhost,100.93.59.21,wisepulse.tail925b8e.ts.net
export no_proxy="$NO_PROXY"
```

仓库里提供了 Agent 访问模板和自检脚本：

- [agent-access.env.example](/Users/mako/Lab/VaultMind/config/agent-access.env.example)
- [install_agent_access_env.sh](/Users/mako/Lab/VaultMind/scripts/install_agent_access_env.sh)
- [check_memoryos_access.sh](/Users/mako/Lab/VaultMind/scripts/check_memoryos_access.sh)

示例：

```bash
./scripts/install_agent_access_env.sh
./scripts/check_memoryos_access.sh ~/.config/memoryos-agent.env
```

当前已确认：

- `http://127.0.0.1:8765/readyz` 在服务器本机可访问
- `http://100.93.59.21:8765/readyz` 在 tailnet 对等端可访问
- 如果客户端启用了 `HTTP_PROXY`/`HTTPS_PROXY`，必须通过 `NO_PROXY` 排除这两个地址

## Hermes Client

当前仓库已经补充了 Hermes 的客户端接入资产：

- [Hermes Integration README](/Users/mako/Lab/VaultMind/clients/hermes/README.md)
- [Hermes MemoryOS Skill](/Users/mako/Lab/VaultMind/clients/hermes/skills/memoryos/SKILL.md)

对 Hermes 的接入结论是：

- Hermes 支持 skill，但默认持久记忆不是单靠 skill 扩展出来的。
- 如果要让 MemoryOS 接管 Hermes 的默认记忆，必须替换 Hermes `memory` 工具背后的 `MemoryStore` 后端。
- 当前实现采用“有 `MEMORYOS_*` 环境变量时走 MemoryOS API，没有时回退本地 `MEMORY.md`/`USER.md` 文件”的兼容模式。

## Remote Status

当前 `wisepulse-tailscale` 的实际部署路径：

```text
/home/mako/VaultMind
```

当前服务默认数据目录：

```text
/home/mako/VaultMind/var/data
```
