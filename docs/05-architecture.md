# 05 · 技术架构

## 技术选型

| 模块 | 技术 | 职责 |
| --- | --- | --- |
| Core | Python 3.11 | 核心业务逻辑 |
| CLI | Typer | 命令入口 |
| Schema | Pydantic | Manifest 校验 |
| Storage | File System + SQLite | 资产和状态 |
| Version | Git + SHA256 | 版本与完整性 |
| Adapter | Python | Agent 配置转换 |
| MCP | MCP Python SDK | Agent 能力发现接口 |
| GUI | Tauri v2 + Svelte 5 | 后续可视化 |

选型理由：

- **Python 3.11**：与 MCP Python SDK、Agent Skills 生态一致，跨平台可用。
- **Typer**：类型注解即 CLI 定义，减少样板。
- **Pydantic**：Manifest 的单一校验来源，同时可生成 JSON Schema。
- **File System + SQLite**：文件是事实来源，SQLite 只做索引与运行状态，避免双写不一致。
- **Git + SHA256**：Git 提供版本历史与协作，SHA256 提供内容级不可变性验证。
- **Tauri v2 + Svelte 5**：GUI 体积小、启动快，且后端可复用 Python Core（通过本地 IPC）。

## 分层架构

```
┌──────────────────────────────────────┐
│  CLI  /  Desktop UI  /  Agent MCP    │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│            CapNest Core              │
│  Registry · Manifest · Resolver      │
│  Validator · Deployment              │
│  Version Manager                     │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│            Adapter Layer             │
│  Codex · Claude Code                 │
│  OpenClaw (planned, Phase 4)         │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│         Canonical Asset Store        │
│  MCP · Skills · Workflows · Profiles │
└──────────────────────────────────────┘
```

### Core

所有业务规则都在 Core，**CLI、GUI、Agent MCP 三个入口共享同一套实现**，不允许各自复制逻辑。

| 组件 | 职责 |
| --- | --- |
| Registry | 资产的登记、索引、检索、元数据 |
| Manifest | 读写与校验 Manifest / Lockfile |
| Resolver | 依赖解析、版本约束求解、目标选择 |
| Validator | Manifest、依赖、路径、权限校验 |
| Deployment | Diff 计算、Apply、Backup、Rollback、漂移与版本落后检测 |
| Version Manager | 内容哈希、版本比较、锁定 |

### Adapter Layer

每个 Adapter 只负责两件事：

1. **读**：把目标 Agent 的现有配置解析成 CapNest 内部结构
2. **写**：把 CapNest 内部结构转换成目标 Agent 的配置格式并写入

Adapter 不做版本决策、不做依赖解析，这些属于 Core。

| Adapter | 阶段 | 目标 | 典型写入内容 |
| --- | --- | --- | --- |
| Codex | 首期（Phase 2） | `~/.codex/` | `skills/` 目录、`config.toml` 中的 MCP 段 |
| Claude Code | 首期（Phase 2） | `~/.claude/` | `skills/` 目录、`.mcp.json` / settings 中的 MCP 段 |
| OpenClaw | 后续（Phase 4） | 待定 | Skills 与工具配置 |

具体路径以实际 Agent 版本的配置结构为准，需在 Phase 0 调研确认后固化到各 Adapter 的测试中。

**AionUi 不是部署目标。** 它是 Agent Workspace，通过 CapNest 的 Discovery 接口消费能力，但 CapNest 不向它写入配置，因此不设 AionUi Adapter。

### Canonical Asset Store

CapNest 内部只有一套资产模型。Adapter 层的「本地结构」与 Agent 的「原生结构」之间通过 Adapter 双向转换，不允许把 Agent 的格式泄漏进 Core。

## 安全策略

1. 不在 Manifest 和 Lockfile 中保存明文 Token、密码
2. 敏感信息使用环境变量或系统密钥库引用
3. 不静默覆盖 Agent 原有配置
4. 每次部署先生成 Diff
5. 修改前自动备份
6. 对未知脚本和外部下载进行安全检查
7. Agent 只能读取和申请操作，不应默认获得资产修改权限

### 实现映射

| 原则 | 实现方式 |
| --- | --- |
| 1 | Manifest Schema 校验时拒绝含疑似密钥的字段值 |
| 2 | 资产配置中使用 `${ENV_VAR}` 引用，部署时按需解析 |
| 3 | `apply` 默认交互式确认；`--yes` 需显式指定 |
| 4 | `plan` 输出 unified diff；`plan` 与 `apply` 接受相同的 `--profile` / `--target` 并共用同一计算函数 |
| 5 | 每次 `apply` 前快照至 `state/backups/<timestamp>/` |
| 6 | 导入时对脚本做静态检查，标记外部下载行为 |
| 7 | CapNest MCP Server 暴露只读 + 申请类工具，写操作需人工确认 |

## 部署状态模型

每次部署产生一条记录（存于 SQLite，并同步写入 `state/deployments/`）：

| 字段 | 说明 |
| --- | --- |
| `id` | 部署 ID |
| `profile` | 关联的 Profile 名 |
| `target` | 目标 Agent |
| `resolved` | 实际部署的资产版本与哈希 |
| `applied_state_hash` | **apply 完成后目标 Agent 配置的哈希**，用于检测外部修改（漂移） |
| `asset_hashes` | 部署时各资产的哈希，用于检测资产更新（版本落后） |
| `diff_hash` | 本次 Diff 的哈希，仅用于审计 |
| `created_at` | 时间戳 |
| `backup_ref` | 对应备份目录 |

### 两种检测，含义不同

两者回答的是不同问题，实现上必须分开：

| 检测 | 问题 | 比对方式 |
| --- | --- | --- |
| **漂移** | Agent 侧配置被外部改动了？ | 重新计算当前 Agent 配置的哈希，与 `applied_state_hash` 比对，不一致即报告 drift，并提示 `plan` / `apply` / `rollback` |
| **版本落后** | CapNest 里的资产更新了？ | 将 `asset_hashes` 与当前 `assets/` 中对应资产的哈希逐一比对，不一致即提示需要重新 `apply` |

注意：`applied_state_hash` 是**应用之后的目标状态哈希**，不是 Diff 的哈希——两者不可互换，否则每次检查都会误报漂移。`diff_hash` 仅作审计留痕，不参与任何判定。

`status` 命令同时汇报这两种检测结果。

## 测试策略

- **Manifest**：Schema 单元测试 + 反例快照
- **Resolver**：版本约束求解的表驱动测试
- **Adapter**：每个 Adapter 对着一份固定的「Agent 原生配置样本」做双向转换的黄金测试
- **Deployment**：Diff → Apply → Rollback 的往返测试，断言还原后与初始状态完全一致
