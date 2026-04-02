# Hermes Client Integration

这个目录存放 Hermes Agent 接入 MemoryOS 的客户端资产。

当前设计结论：

- Hermes 确实支持 `skill`，用户级技能目录位于 `~/.hermes/skills/`。
- 但 Hermes 的默认持久记忆不是单纯靠 skill 扩展出来的，而是内建 `memory` 工具和 `MemoryStore` 后端。
- 因此想让 MemoryOS 接管 Hermes 默认记忆，必须替换 `tools/memory_tool.py` 的后端，而不是只安装一个新 skill。

当前接入方案：

1. Hermes 的 `memory` 工具保持原接口不变。
2. 当检测到 `MEMORYOS_BASE_URL`、`MEMORYOS_API_KEY`、`MEMORYOS_AGENT_ID` 等环境变量时，`MemoryStore` 自动改走 MemoryOS API。
3. 若未配置这些变量，则继续回退到原本的 `~/.hermes/memories/MEMORY.md` / `USER.md` 文件后端。

配套 skill 位于：

- [SKILL.md](/Users/mako/Lab/VaultMind/clients/hermes/skills/memoryos/SKILL.md)
- [Hermes Patch](/Users/mako/Lab/VaultMind/clients/hermes/patches/hermes-memoryos.patch)

这份 skill 主要用于：

- 告诉 Hermes 当前环境里 `memory` 已由 MemoryOS 接管
- 约束模型继续使用原生 `memory` 工具接口，而不是自己发明一套新流程
- 在需要排查时提供调试命令

补丁文件则用于把 Hermes 自带的 `tools/memory_tool.py` 切换为 MemoryOS 后端优先、文件后端回退的兼容实现。
