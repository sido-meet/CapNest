# CapNest

**Personal Capability Infrastructure**

> Build once. Reuse across every agent.

让个人积累的 AI 能力独立于 Agent 存在，可以统一管理、组合、版本化，并被不同 Agent 随时发现和使用。

| 项目 | 值 |
| --- | --- |
| 产品形态 | Local-first |
| 核心对象 | MCP / Skill / Workflow |
| 首期平台 | Windows |
| 首期 Agent | Codex / Claude Code |
| 当前阶段 | 产品设计与 MVP 规划（Phase 0） |

---

## 1. 为什么

今天的 Agent 生态里，每个 Agent 都有自己的 Skill、MCP、Plugin 和配置管理机制：

- Codex 有自己的 Skills 和 MCP 配置
- Claude Code 有自己的 Skills 和 MCP 配置
- AionUi 有自己的 Skill Catalog 和 MCP 管理
- OpenClaw 有自己的 Skills 和工具体系

结果是：**用户在每个 Agent 中重复配置、复制和维护同一批能力**。

但这些能力本质上属于用户，而不是属于某个 Agent。

CapNest 做的事情很简单：**把个人积累的 AI 能力从 Agent 中解耦出来，形成独立的、可持续积累的资产。**

我们不重新开发 Agent，我们关注的是它们之下的**公共能力资产层**。

## 2. 四个核心价值

| 价值 | 说明 |
| --- | --- |
| **Capability Persistence** | 能力独立存储，不依附于某个 Agent；更换 Agent 不需要重新建设 |
| **Capability Composition** | MCP、Skill、Workflow 可组合成 Profile，形成可复用能力集合 |
| **Capability Portability** | 一份资产适配多个 Agent，统一管理版本、依赖、部署与回滚 |
| **Capability Discovery** | Agent 可通过 MCP 搜索、查询、了解并申请使用已有能力 |

## 3. 核心资产模型

第一版只定义三种核心能力，以及一种组合对象。

| 类型 | 定义 | 示例 |
| --- | --- | --- |
| MCP Server | 提供工具和数据访问 | QQ、Database、KeePassXC |
| Skill | 提供完成任务的方法和知识 | SQL Analysis、Paper Review |
| Workflow | 描述多步骤任务流程 | Literature Review Pipeline |
| Profile | 组合多种能力，是部署的单位 | Research、Developer、Data Agent |

明确的边界：

- **Tool** 是 MCP Server 暴露的子资源，不单独设计 Tool Runtime
- **Skill** 继续遵循 Agent Skills 原生规范
- **MCP** 继续遵循 MCP 原生规范
- **Workflow** 首期只定义描述和依赖，不开发执行引擎
- **Profile** 用于组合和分发能力

### 资产目录

文件系统是唯一事实来源，SQLite 只负责索引和运行状态。

```
CapNest/
├── assets/
│   ├── mcp/          # qq/  database/  keepassxc/      每个目录自带 capability.yaml
│   ├── skills/       # paper-review/  sql-analysis/  research-assistant/
│   └── workflows/    # literature-review/  data-diagnosis/
├── profiles/         # research.yaml  research.lock.yaml  developer.yaml  data-agent.yaml
├── state/            # capnest.db  deployments/  backups/  logs/
└── config.yaml
```

设计原则：

- `assets/`：真正的能力内容，**每个资产目录自带一份 `capability.yaml`**
- `profiles/`：能力组合（`kind: CapabilityProfile`）及其锁文件 `*.lock.yaml`
- `state/`：部署状态、索引和日志，其中 `state/backups/` 保存 Agent 原有配置备份

`assets/` 应当可以独立于 CapNest 使用，并通过 Git 管理。资产描述与资产内容放在一起，因此整个 `assets/` 目录拷走即可迁移。

## 4. CLI（规划中）

CLI 是第一版的唯一入口，GUI 排在后面。

```bash
# 初始化
capnest init

# 导入资产
capnest add skill ./paper-review
capnest add mcp ./database
capnest add workflow ./data-diagnosis

# 查看和搜索
capnest list
capnest search "SQL analysis"

# 检查资产
capnest validate

# 创建能力组合
capnest profile create research

# 预览部署
capnest plan --profile research --target codex,claude-code

# 应用部署（接受与 plan 完全相同的 --profile / --target）
capnest apply --profile research --target codex,claude-code

# 查看状态
capnest status

# 回滚
capnest rollback
```

## 5. 技术栈

| 模块 | 技术 | 职责 |
| --- | --- | --- |
| Core | Python 3.11 | 核心业务逻辑 |
| CLI | Typer | 命令入口 |
| Schema | Pydantic | Manifest 校验 |
| Storage | File System + SQLite | 资产与状态 |
| Version | Git + SHA256 | 版本与完整性 |
| Adapter | Python | Agent 配置转换 |
| MCP | MCP Python SDK | Agent 能力发现接口 |
| GUI | Tauri v2 + Svelte 5 | 后续可视化 |

```
CLI / Desktop UI / Agent MCP
          │
      CapNest Core  (Registry · Manifest · Resolver · Validator · Deployment · Version Manager)
          │
      Adapter Layer  (Codex / Claude Code / OpenClaw*)
          │
      Canonical Asset Store  (MCP / Skills / Workflows / Profiles)
```

首期只落地 **Codex** 与 **Claude Code** 两个 Adapter；OpenClaw 计划在 Phase 4 补齐。**AionUi 不是部署目标**——它是 Agent Workspace，通过 CapNest 消费能力，不接受 CapNest 写入配置。

## 6. 安全原则

1. 不在 Manifest 和 Lockfile 中保存明文 Token、密码
2. 敏感信息使用环境变量或系统密钥库引用
3. 不静默覆盖 Agent 原有配置
4. 每次部署先生成 Diff
5. 修改前自动备份
6. 对未知脚本和外部下载进行安全检查
7. Agent 只能读取和申请操作，不应默认获得资产修改权限

## 7. 路线图

| 阶段 | 目标 | 验收 |
| --- | --- | --- |
| Phase 0 | 竞品验证与技术预研 | 技术选型文档、Manifest 草案、竞品验证记录 |
| Phase 1 | Local Registry | 所有个人能力能统一登记、搜索、组合 |
| Phase 2 | Cross-Agent Deployment | 同一 Profile 能稳定部署到两个 Agent |
| Phase 3 | Agent Discovery | Codex、Claude Code 可主动发现 CapNest 中的能力 |
| Phase 4 | 产品化 | 完整的个人本地能力管理产品 |

详见 [`docs/06-roadmap.md`](docs/06-roadmap.md)。

## 8. 文档

| 文档 | 内容 |
| --- | --- |
| [docs/01-positioning.md](docs/01-positioning.md) | 产品定位、边界与核心价值 |
| [docs/02-asset-model.md](docs/02-asset-model.md) | 核心资产模型与目录规范 |
| [docs/03-capability-manifest.md](docs/03-capability-manifest.md) | 统一 Capability Manifest 规范 |
| [docs/04-mvp.md](docs/04-mvp.md) | MVP 范围、使用场景与 CLI 设计 |
| [docs/05-architecture.md](docs/05-architecture.md) | 技术架构、模块职责与安全策略 |
| [docs/06-roadmap.md](docs/06-roadmap.md) | 五阶段开发路线与验收标准 |
| [docs/07-acceptance.md](docs/07-acceptance.md) | MVP 验收标准与首个演示项目 |
| [docs/08-competitive.md](docs/08-competitive.md) | 竞品策略与复用原则 |


## License

[MIT](LICENSE)
