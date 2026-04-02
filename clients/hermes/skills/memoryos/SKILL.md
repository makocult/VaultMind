---
name: memoryos
description: Operate Hermes persistent memory through the MemoryOS-backed memory tool and use API checks only for debugging.
version: 1.0.0
author: VaultMind
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [memory, memoryos, vaultmind, profile]
---

# MemoryOS Backend

In this Hermes installation, the built-in `memory` tool is backed by MemoryOS when the `MEMORYOS_*` environment variables are configured.

## How To Use It

- Keep using the normal `memory` tool for durable facts.
- Save user preferences and personal details to target `user`.
- Save environment facts, project conventions, and stable lessons to target `memory`.
- Continue treating `session_search` as the place for task logs and past transcript recall.

## Important Rule

Do not invent a second memory workflow if `memory` already works.

When you want to save durable information:

- use `memory(action=\"add\", target=\"user\"|\"memory\", ...)`
- use `replace` to update an existing durable fact
- use `remove` to delete stale durable facts

## What Changed

- Old backend: `~/.hermes/memories/MEMORY.md` and `USER.md`
- New backend when configured: MemoryOS API
- The `memory` tool contract stays the same, so existing behavior should feel unchanged from the model's perspective

## Debugging

If memory behavior looks wrong, verify the backend before changing strategy:

```bash
env | grep '^MEMORYOS_'
curl -sS http://127.0.0.1:8765/readyz
curl -sS -H "X-Api-Key: $MEMORYOS_API_KEY" -H "X-Agent-Id: $MEMORYOS_AGENT_ID" \
  -H "Content-Type: application/json" \
  -d '{"limit":20,"tags":["hermes-memory"]}' \
  http://127.0.0.1:8765/api/v1/memory/list
```

If the backend is healthy, keep using the normal `memory` tool instead of bypassing it manually.
