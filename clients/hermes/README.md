# Hermes Client Integration

这个目录存放 Hermes Agent 以 `skill` 方式接入 VaultMind 的客户端资产。

当前采用的正式方案是“双记忆系统并行”：

- Hermes 原生 `memory` 保持不变。
- VaultMind 作为第二套外部记忆系统，由 skill 指导 Hermes 通过脚本调用 API。
- 两套记忆可以同时使用，但互不替换、互不接管。

这样做的原因很明确：

- Hermes 支持 `skill`，用户级技能目录位于 `~/.hermes/skills/`。
- 但 Hermes 默认持久记忆不是稳定的外部扩展点。
- 如果强行接管默认记忆，就必须改 Hermes 源码，升级时风险不可控。

所以 Hermes 侧的推荐模式是：

1. 用 Hermes 原生 `memory` 保存它自己的轻量本地记忆。
2. 用 VaultMind skill 处理更强的跨会话检索、项目事实、结构化长期记忆。
3. 在需要的时候双写，两边同时保存。

当前配套 skill 位于：

- [Memory Category Description](/Users/mako/Lab/VaultMind/clients/hermes/skills/memory/DESCRIPTION.md)
- [VaultMind Skill](/Users/mako/Lab/VaultMind/clients/hermes/skills/vaultmind/SKILL.md)
- [VaultMind Script](/Users/mako/Lab/VaultMind/clients/hermes/skills/vaultmind/scripts/vaultmind_memory.py)
- [VaultMind Env Example](/Users/mako/Lab/VaultMind/clients/hermes/vaultmind.env.example)

这套资产的作用是：

- 让 Hermes 明确知道 VaultMind 是并行记忆，而不是默认 memory 的替代品
- 提供可直接从 `terminal` 工具调用的记忆脚本
- 避免对 Hermes 上游源码做任何侵入式修改

为了让 Hermes 真正“意识到”自己有两套记忆，推荐使用三层提示：

1. `SOUL.md` 中加入常驻规则：明确说明原生 `memory` 和 VaultMind 的分工。
2. Hermes 原生 `MEMORY.md` 中加入一条稳定事实：提醒自己遇到历史/项目上下文问题时优先考虑查 VaultMind。
3. skill 索引层加入 `memory/DESCRIPTION.md` 和 `vaultmind/SKILL.md`：让技能列表本身也写清楚“两套并行记忆”的关系。
