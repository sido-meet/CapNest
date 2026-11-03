# 005 Adapters

本文描述两个目标 Agent 的**真实配置格式**与读写方式。

这些格式全部来自本机实测：用 `CLAUDE_CONFIG_DIR` / `CODEX_HOME` 指向临时目录后调用两个 Agent 的 CLI，观察写入结果。实测未触碰真实配置。Agent 版本升级后格式可能变化，因此 Adapter 的行为由 golden fixture 测试锁定（见 [003 Architecture](003-architecture.md) 的测试策略）。

## Codex

### MCP 配置

存储位置：`~/.codex/config.toml`，键为 `[mcp_servers.<name>]`。

stdio 类型：

```toml
[mcp_servers.capnest_probe]
command = "echo"
args = ["hi"]
```

HTTP 类型：

```toml
[mcp_servers.probe_http]
url = "https://example.com/mcp"
```

真实 `config.toml` 里还观察到的同段字段：

| 字段 | 用途 |
| --- | --- |
| `command` / `args` | stdio 启动命令 |
| `env` | 字面量环境变量表 |
| `env_vars` | **环境变量名列表**（从宿主环境透传，不是值） |
| `url` | HTTP 端点 |
| `http_headers` | HTTP 头 |
| `enabled` | 是否启用 |
| `startup_timeout_sec` | 启动超时 |
| `default_tools_approval_mode` | **Server 级**的工具审批策略（如 `prompt`） |

`default_tools_approval_mode` 名字里带 tools，但它挂在 Server 段下，是**该 Server 全部 Tool 的统一策略**，不是单个 Tool 的条目。这印证了 [001 Domain model](001-domain.md) 的粒度结论。

### Skills

- 位置：`~/.codex/skills/<name>/SKILL.md`
- `.system/` 子目录是内置 skill，**CapNest 绝不触碰**
- frontmatter 只有两个字段：

```markdown
---
name: "imagegen"
description: "Generate or edit raster images when the task benefits from …"
---
```

- 启停通过 `config.toml` 的 `[[skills.config]]` 数组控制（`path` + `enabled`）

### 写入 `config.toml` 的正确做法

`config.toml` 是**共享文件**，里面有用户手写的注释和大量无关配置。必须用 `tomlkit` 做文档级编辑：

```python
from tomlkit import parse as toml_parse
from tomlkit.items import Table

doc = toml_parse(original_text)

servers = doc.get("mcp_servers")
if servers is None:
    servers = Table()
    doc["mcp_servers"] = servers

servers[name] = {"command": cmd, "args": args, "env": env}
```

写入前后的双重保护：

1. 编辑在内存中的副本上进行，不动原文件
2. 序列化后与原文做 diff，**只允许 `mcp_servers.<name>` 相关的行变化**；出现任何预期外变化 → 中止并报错

### 落点与能力矩阵

| 资产类型 | 落点 |
| --- | --- |
| Skill | `~/.codex/skills/<name>/` |
| MCP Server | `~/.codex/config.toml` 的 `[mcp_servers.<name>]` |

```python
TargetCapabilities(
    target="codex",
    supports={CapabilityType.SKILL, CapabilityType.MCP_SERVER},
    deployment_modes={DeploymentMode.COPY, DeploymentMode.SYMLINK},
    skills_path="~/.codex/skills",
    mcp_backend="toml",
)
```

Skill 部署：目标已存在且不是 CapNest 管理的 → 报错（退出码 7），不覆盖；已存在且是 CapNest 管理的 → 目录级比对，有差异则整目录替换（先备份）。

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
- frontmatter 与 Codex 相同（`name` + `description`）
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

### 落点与能力矩阵

| 资产类型 | 落点 |
| --- | --- |
| Skill | `~/.claude/skills/<name>/` |
| MCP Server | `~/.claude.json` 顶层 `mcpServers.<name>` |

```python
TargetCapabilities(
    target="claude-code",
    supports={CapabilityType.SKILL, CapabilityType.MCP_SERVER},
    deployment_modes={DeploymentMode.COPY, DeploymentMode.SYMLINK},
    skills_path="~/.claude/skills",
    mcp_backend="json",
)
```

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

| 归一化字段 | Codex | Claude Code |
| --- | --- | --- |
| `transport=stdio` | `command` + `args` + `env` | `type: "stdio"` + `command` + `args` + `env` |
| `transport=http` | `url` + `http_headers` | `type: "http"` + `url` + `headers` |

**密钥处理**：明文密钥不进 Manifest。资产里写 `${ENV_VAR}`，部署时解析为环境变量的**值**（Codex 用 `env_vars` 只写变量名更好，但为兼容 Claude Code 的 `env`，v1 统一解析后写入 `env`）。`${ENV_VAR}` 未定义时**报错中止**，不写空值。

## Adapter 协议

```python
@dataclass(frozen=True)
class TargetCapabilities:
    target: str
    supports: set[CapabilityType]
    deployment_modes: set[DeploymentMode]
    skills_path: str | None
    mcp_backend: Literal["toml", "json"] | None
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

## 两个 Agent CLI 的命令面

| CLI | 子命令 | 关键选项 |
| --- | --- | --- |
| `codex mcp` | `list` `get` `add` `remove` `login` `logout` | `--url` / `--env KEY=VALUE` / `-- <COMMAND>...` |
| `claude mcp` | `list` `get` `add` `remove` | `--transport http` / `-e/--env` / `-H/--header` / `-s/--scope local\|user\|project` |

**CapNest 不调用这两个 CLI 来做部署**——CLI 直接写盘，没有 dry-run、没有 diff、没有回滚，正好是 CapNest 需要的反面。CLI 只用于 `doctor` 里的版本探测。

## M0 必须完成的三项实测

这三条是 Adapter 规格的证据来源，也是 M2 风险的直接来源。**不完成不要进入 M2。**

| # | 实测 | 目的 | 产出 |
| --- | --- | --- | --- |
| 1 | 分别用 Codex 与 Claude Code 自己的 CLI 把同一个 skill + 一个 MCP server 装进去 | 抓取两份目标配置文件的**真实样本** | `tests/fixtures/codex_config.toml`、`tests/fixtures/claude.json` |
| 2 | 确认 Codex `config.toml` 与 Claude Code 配置文件在「两个工具同时写」时的合并与冲突规则 | 弄清共享配置的合并语义 | 本文的补遗 + fixture 样本 |
| 3 | 确认 Codex CLI 版本对 `.codex-plugin/plugin.json` 的支持程度 | 决定 plugin 部署形态的排期 | plugin 部署形态是否进入 v0.2 的结论 |

实测脚本放在 `scripts/phase0_probe.ps1`，**必须用沙箱化的 `CLAUDE_CONFIG_DIR` / `CODEX_HOME`**，不得触碰真实配置。

## 下一个

[006 CLI](006-cli.md) — 用户如何调用这一切。