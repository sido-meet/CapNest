# 005 Adapters

本文描述两个目标 Agent 的**真实配置格式**与读写方式。

这些格式全部来自本机实测：用 `CLAUDE_CONFIG_DIR` / `CODEX_HOME` 等环境变量把 Agent 的配置目录指向临时目录后调用其 CLI，观察写入结果。实测未触碰真实配置。Agent 版本升级后格式可能变化，因此 Adapter 的行为由 golden fixture 测试锁定（见 [003 Architecture](003-architecture.md) 的测试策略）。

## v1 的两个目标

| Target | 是什么 | 为什么是它 |
| --- | --- | --- |
| `mcode` | MiniMax Code | 与 Claude Code 是两个独立实现，都遵循 Agent Skills 规范，且都不是 CapNest 的开发宿主 |
| `claude-code` | Claude Code | 同上；且它的用户级 MCP 配置是共享大文件，正好覆盖最难的那种写入场景 |

**为什么 v1 不包含 `codex`**：CapNest 本身就在 Codex 里开发。把 CapNest 部署进 `~/.codex` 等于让被测对象改写开发宿主自己——技能目录会被热加载，配置会被并发读写，测试结果不可信；而且「跨 Agent 一致性」的价值恰恰体现在**两个不同的 Agent**上，其中一个是自己就退化成了自测。Codex 的 Adapter 保留在 v0.2，用来验证「增加第三个目标」的实际成本。

## MiniMax Code（`mcode`）

### 概况

| 项 | 值 |
| --- | --- |
| 版本 | 0.6.2 |
| 安装目录 | `~/.minimax-code/`（只放安装产物与版本，不放配置） |
| **数据目录** | **`~/.minimax/`** |
| 用户配置 | `~/.minimax/config.yaml` |
| CLI | `mcode init` `exec` `acp` `login` `logout` `update` `provider` `plugin` |

**注意**：`~/.minimax-code/` 是安装目录，`~/.minimax/` 才是配置与数据目录。两者都在用户主目录下，只有一个字母之差，极易写错。

### Skills

| 位置 | 归属 | CapNest 是否可写 |
| --- | --- | --- |
| `~/.minimax/skills/<name>/` | 用户级 | **是**（v1 落点） |
| `~/.minimax/.builtin-skills/` | 内置 | **否**，绝不触碰 |
| `~/.minimax/agents/<agent>/skills/` | agent 级 | 否 |
| `<workspace>/.minimax/skills/` | 工作区级 | 否 |
| `<workspace>/.claude/skills/` | 工作区级（兼容读取） | 否 |
| `<workspace>/.agents/skills/` | 工作区级（兼容读取） | 否 |

`~/.minimax/skills/` 与 `~/.minimax/.builtin-skills/` 是同级的两个目录，**内置目录永远不碰**——这与 Codex 的 `.system/` 是同一条规则。

### frontmatter

用户 skill 的 frontmatter：

```markdown
---
name: manim
description: |
  用 Manim Community 把想法做成解释型动画：分镜 → 场景代码 → 预览渲染 → 中文 TTS 配音 → 烧录字幕 → 成片 mp4。…
descriptions:
  zh-Hans: "用 Manim 制作讲解动画：分镜、场景代码、预览渲染、中文配音、字幕、mp4。"
displayNames:
  zh-Hans: "Manim 动画视频"
---
```

- `name` + `description` 必需
- `descriptions` / `displayNames` 是**可选的多语言扩展**，键为 BCP-47 语言标签

**CapNest 只写 `name` 与 `description`**。资产自带的其它 frontmatter 字段原样保留，不覆盖、不删除——它们是资产的一部分，删掉就改变了资产内容。

### MCP

| 位置 | 用途 |
| --- | --- |
| `~/.minimax/config.yaml` 的 `mcpServers` 段 | 用户级 MCP 配置 |
| plugin 目录下的 `mcp.json` | 插件自带 MCP，wrapper 结构为 `{$schema, mcpServers}` |
| `<workspace>/.mcp.json` | 项目级 MCP 配置 |

`mcode` **没有** `mcode mcp` 子命令，MCP 只能通过配置文件或 plugin 声明。因此 MCP 的落点需要实测确认（第一刀的实测任务 T0.9）。

### CLI 命令面

| CLI | 子命令 |
| --- | --- |
| `mcode plugin` | `list` `add` `remove` `enable` `disable` `marketplace` |

没有 MCP 管理命令，也没有 dry-run / diff / rollback——正好是 CapNest 需要的反面。CLI 只用于 `doctor` 里的版本探测。

## Claude Code

### MCP 配置

存储位置：`~/.claude.json`，顶层键 `mcpServers`（user scope）。

stdio 类型：

```json
"mcpServers": {
  "capnest_probe": {
    "type": "stdio",
    "command": "echo",
    "args": ["hi"],
    "env": {}
  }
}
```

HTTP 类型：

```json
"probe_http": {
  "type": "http",
  "url": "https://example.com/mcp"
}
```

带请求头：

```json
"probe_hdr": {
  "type": "http",
  "url": "https://example.com/mcp",
  "headers": { "X-Api-Key": "secret" }
}
```

**`~/.claude.json` 是 Adapter 最大的技术风险**，三个问题：

1. 文件很大（真实环境约 26k 行），且混入大量运行时状态（`tipsHistory`、`skillUsage`、`projects.*` 等）
2. 被 Claude Code 高频写入，与 CapNest 存在**写冲突**的可能
3. 同一文件里还有**项目级** `projects.<path>.mcpServers`；CapNest 只碰顶层 user scope

另外，Claude Code CLI 自己写这个文件时会先备份（实测生成了 `backups/.claude.json.backup.<timestamp>`）。

### Skills

- 位置：`~/.claude/skills/<name>/SKILL.md`
- frontmatter 与 mcode 相同（`name` + `description`）
- **存在嵌套目录**（实测：`~/.claude/skills/ai-research-skills/0-autoresearch-skill/SKILL.md`）。v1 只支持**顶层单层**的 skill 目录，嵌套视为不支持并在 `validate` 阶段报 warn，且拒绝覆盖

### 定点块编辑（关键设计）

**不重写整个 `~/.claude.json`。** 原因：文件巨大、混有运行时状态、被高频写入；整体重排格式会让 diff 变成噪音，也放大写冲突的损失面。

算法：

```
1. 读原文为字符串
2. 定位顶层 "mcpServers" 键的块边界：
   - 用 json.JSONDecoder.raw_decode 从键名后的冒号处解析出该键的完整值，
     从而精确知道它的起始与结束偏移
3. 若不存在该键：在顶层对象的合适位置插入 "mcpServers": { … }
4. 解析该块的 JSON → dict
5. 在 dict 内做 upsert / delete
6. 序列化新块（indent=2，与原文件风格一致）
7. 用新块替换原文的对应区间，其余字节逐字保留
```

这样得到的 diff 只有 `mcpServers` 块内的几行，回滚时也能精确还原。

**并发保护**：写前检查文件 mtime 与读取时一致；不一致则中止并提示重试。

### CLI 命令面

| CLI | 子命令 | 关键选项 |
| --- | --- | --- |
| `claude mcp` | `list` `get` `add` `remove` | `--transport http` / `-e/--env` / `-H/--header` / `-s/--scope local\|user\|project` |

同样不用于部署，只用于 `doctor` 的版本探测。

## MCP 定义的归一化

两个 Agent 的 MCP 格式不同，CapNest 内部统一为：

```python
@dataclass(frozen=True)
class McpServerDef:
    name: str
    transport: Literal["stdio", "http"]
    command: str | None
    args: list[str]
    env: dict[str, str]
    url: str | None
    headers: dict[str, str]
```

| 归一化字段 | mcode | Claude Code |
| --- | --- | --- |
| `transport=stdio` | `command` + `args` + `env` | `type: "stdio"` + `command` + `args` + `env` |
| `transport=http` | `url` + `headers` | `type: "http"` + `url` + `headers` |

mcode 一侧的具体键名在第二刀实测后填实。

**密钥处理**：明文密钥不进 Manifest。资产里写 `${ENV_VAR}`，部署时解析为环境变量的**值**。`${ENV_VAR}` 未定义时**报错中止**，不写空值。

## Adapter 协议

```python
@dataclass(frozen=True)
class TargetCapabilities:
    target: str
    supports: set[CapabilityType]
    deployment_modes: set[DeploymentMode]
    skills_path: str | None
    mcp_backend: Literal["yaml", "json"] | None
    notes: str = ""


@dataclass(frozen=True)
class TargetState:
    skills: dict[str, str]            # skill 名 → 内容哈希
    mcp_servers: dict[str, dict]      # server 名 → 归一化定义
    config_fingerprint: str


class Adapter(Protocol):
    target: str
    def capabilities(self) -> TargetCapabilities: ...
    def read(self) -> TargetState: ...
    def plan(self, desired: DesiredState) -> list[WriteIntent]: ...
    def verify(self, expected: TargetState) -> VerificationResult: ...
```

### 职责边界

| 属于 Adapter | 属于 Core（`deployment/`） |
| --- | --- |
| 读懂目标配置格式 | diff 计算 |
| 归一化成 `TargetState` | 原子写与预写事务 |
| 生成 `WriteIntent` | 备份与回滚 |
| 声明能力矩阵 | 归属证明 |
| 校验写回结果 | 部署状态记录 |

## 后续目标：Codex（v0.2）

以下为本机实测结论，保留以便将来实现 Adapter 时不必重新调研：

| 项 | 值 |
| --- | --- |
| MCP 配置 | `~/.codex/config.toml`，键 `[mcp_servers.<name>]` |
| stdio | `command` + `args` |
| http | `url` |
| 同段其它字段 | `env`、`env_vars`（变量名列表）、`http_headers`、`enabled`、`startup_timeout_sec`、`default_tools_approval_mode`（**Server 级**的工具审批策略） |
| Skills | `~/.codex/skills/<name>/SKILL.md`，frontmatter 仅 `name` + `description` |
| 内置 skills | `~/.codex/skills/.system/`，**绝不触碰** |
| 启停 | `config.toml` 的 `[[skills.config]]`（`path` + `enabled`） |
| CLI | `codex mcp list\|get\|add\|remove\|login\|logout` |

写入 `config.toml` 必须用 `tomlkit` 做文档级编辑：`tomllib` 只读，普通 `toml` 会重排格式，只有 tomlkit 能 round-trip 用户手写的注释。

## M0 必须完成的三项实测

这三条是 Adapter 规格的证据来源，也是 M2 风险的直接来源。**不完成不要进入 M2。**

| # | 实测 | 目的 | 产出 |
| --- | --- | --- | --- |
| 1 | 分别用 `mcode` 与 `claude` 自己的 CLI 安装同一个 skill 与一个 MCP server | 抓取两份目标配置文件的**真实样本** | `tests/fixtures/mcode_config.yaml`、`tests/fixtures/claude.json` |
| 2 | 确认 mcode 的 `config.yaml` 与 Claude Code 的 `.claude.json` 在「两个工具同时写」时的合并与冲突规则 | 弄清共享配置的合并语义 | 本文的补遗 + fixture 样本 |
| 3 | 确认 mcode 用户级 MCP 配置的落点（`config.yaml` 的 `mcpServers` 段，或独立的 `mcp.json`） | 决定 MCP Adapter 写哪里 | MCP 落点的结论 |

实测脚本放在 `scripts/phase0_probe.ps1`，**必须用沙箱化的环境变量指向临时目录**，不得触碰真实配置。

## 下一个

[006 CLI](006-cli.md) — 用户如何调用这一切。