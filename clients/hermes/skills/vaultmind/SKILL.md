---
name: vaultmind
description: Use VaultMind as a parallel long-term memory system alongside Hermes native memory.
version: 1.0.0
author: VaultMind
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [memory, vaultmind, retrieval, long-term-memory]
---

# VaultMind Parallel Memory

In this Hermes installation, VaultMind is a second memory system that runs in parallel with Hermes native `memory`.

## Core Rule

Do not replace Hermes native `memory`.

Use both systems together:

- Hermes `memory`: small local durable notes that fit Hermes's native workflow
- VaultMind: richer cross-session recall, project memory, structured long-term memory, retrieval before action

## When To Use VaultMind

- Before answering questions that may depend on older project decisions or prior sessions
- When the user asks what was decided before, what preferences were established, or what a previous plan was
- When you want stronger recall than Hermes native memory alone can provide
- When a fact should be durable across systems and future sessions

## Recommended Pattern

1. Recall from VaultMind before important work.
2. Answer or act.
3. If a new durable fact emerged, save it to VaultMind.
4. If it is also useful to Hermes locally, save it to Hermes native `memory` too.

## Script Entry Point

Use the terminal tool to run:

```bash
python ~/.hermes/skills/memory/vaultmind/scripts/vaultmind_memory.py health
python ~/.hermes/skills/memory/vaultmind/scripts/vaultmind_memory.py recall --query "What did we decide about deployment?" --limit 5 --format json
python ~/.hermes/skills/memory/vaultmind/scripts/vaultmind_memory.py remember --text "The user prefers concise release notes." --kind opinion --tag user-preference --format json
```

## Retrieval Guidance

Before making decisions that may rely on prior context, prefer:

```bash
python ~/.hermes/skills/memory/vaultmind/scripts/vaultmind_memory.py recall --query "<question>" --limit 5 --format json
```

Use `--mode agentic` when the query is broad or ambiguous and you want deeper retrieval.

## Save Guidance

Use VaultMind for information such as:

- project decisions
- architecture constraints
- user preferences that matter later
- known environment facts
- repeated workflow conventions

Use:

```bash
python ~/.hermes/skills/memory/vaultmind/scripts/vaultmind_memory.py remember \
  --text "<durable fact>" \
  --kind semantic \
  --tag hermes-skill \
  --entity "<important entity>" \
  --format json
```

For user preferences, use `--kind opinion`.

## Do Not Do This

- Do not assume VaultMind has replaced Hermes native memory.
- Do not patch Hermes source just to use VaultMind.
- Do not invent a third memory workflow if the provided script already works.

## Debugging

If VaultMind seems unavailable:

```bash
python ~/.hermes/skills/memory/vaultmind/scripts/vaultmind_memory.py health
env | grep '^VAULTMIND_'
env | grep '^NO_PROXY'
```

If `health` succeeds, continue using the script through the terminal tool.
