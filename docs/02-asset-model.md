# 02 · 核心资产模型

## 三种能力 + 一种组合

第一版只定义三种核心能力，以及一种组合对象。

| 类型 | 定义 | 示例 | 原生规范 |
| --- | --- | --- | --- |
| MCP Server | 提供工具和数据访问 | QQ、Database、KeePassXC | MCP |
| Skill | 提供完成任务的方法和知识 | SQL Analysis、Paper Review | Agent Skills |
| Workflow | 描述多步骤任务流程 | Literature Review Pipeline | CapNest 自定义（草案） |
| Profile | 组合多种能力，是部署的单位 | Research、Developer、Data Agent | CapNest 自定义 |

### 边界说明

- **Tool** 是 MCP Server 暴露的子资源，不单独设计一套 Tool Runtime。
- **Skill** 继续遵循 Agent Skills 原生规范，我们只做登记与分发。
- **MCP** 继续遵循 MCP 原生规范，我们只做登记与分发。
- **Workflow** 首期只定义描述和依赖，不开发执行引擎。
- **Profile** 用于组合和分发能力，是部署的单位。

核心原则：**统一描述，不强制统一执行。** 尤其是 Workflow，不应该为了追求统一而强行兼容所有执行引擎。

### 粒度：只登记可独立安装的那一层

资产模型只覆盖「可独立安装、可独立版本化」的那一层，更细的粒度不单独建模。

| 层级 | 是否建模 | 原因 |
| --- | --- | --- |
| MCP Server | 是 | 独立可安装，有独立版本 |
| └─ Tool | 否 | 由 Server 的代码在运行时注册，名字随 Server 版本变化，不稳定 |
| Skill | 是 | 独立可安装的目录 |
| └─ Skill 内部文件 | 否 | 是 Skill 的组成部分，不是独立资产 |
| Workflow | 是 | 独立可安装的目录 |

两个直接后果：

1. 登记一个 MCP Server 即获得它暴露的全部 Tool，**不需要枚举 Tool**。
2. Tool 名不是稳定标识，不能作为资产主键——`mcp__<server>__<tool>` 中的 server 别名与 tool 注册名两层都会变。

Skill 与 Tool 也在不同层：Skill 是给模型看的方法与知识（以文档形式注入上下文），Tool 是可调用的函数。Skill **引用** Tool，而不是包含 Tool。

### Bundle 不作为独立对象

早期草案中 Profile 与 Bundle 两个组合概念职责重叠。本版**只保留 Profile** 作为组合与部署单位；「Bundle」一词只在描述「一个可分发的组合产物」时作为口语说法使用，不对应独立的 Manifest `kind`。

Profile 与 Manifest 的对应关系见 [`03-capability-manifest.md`](03-capability-manifest.md)。

## 资产目录

文件系统是唯一事实来源（single source of truth），SQLite 只负责索引和运行状态。

```
CapNest/
│
├── assets/
│   ├── mcp/
│   │   ├── qq/
│   │   │   ├── capability.yaml      ← kind: Capability
│   │   │   └── server.json
│   │   ├── database/
│   │   └── keepassxc/
│   │
│   ├── skills/
│   │   ├── paper-review/
│   │   │   ├── capability.yaml      ← kind: Capability
│   │   │   └── SKILL.md
│   │   ├── sql-analysis/
│   │   └── research-assistant/
│   │
│   └── workflows/
│       ├── literature-review/
│       │   ├── capability.yaml      ← kind: Capability
│       │   └── workflow.yaml
│       └── data-diagnosis/
│
├── profiles/
│   ├── research.yaml                ← kind: CapabilityProfile
│   ├── research.lock.yaml           ← kind: CapabilityLock
│   ├── developer.yaml
│   └── data-agent.yaml
│
├── state/
│   ├── capnest.db
│   ├── deployments/
│   ├── backups/
│   └── logs/
│
└── config.yaml
```

### 目录职责

| 目录 | 内容 | 是否纳入版本控制 |
| --- | --- | --- |
| `assets/` | 真正的能力内容，每个资产目录自带 `capability.yaml` | 建议 |
| `profiles/` | 能力组合定义及其锁文件 | 建议 |
| `state/` | 部署状态、索引和日志 | 忽略 |
| `state/backups/` | Agent 原有配置备份 | 忽略 |
| `config.yaml` | CapNest 自身配置 | 建议 |

### 设计原则

- `assets/`：真正的能力内容。
- `profiles/`：能力组合（Profile）及其锁文件（Lockfile）。
- `state/`：部署状态、索引和日志，其中 `state/backups/` 保存 Agent 原有配置备份。

**资产目录应当可以独立于 CapNest 使用和通过 Git 管理。** 资产描述与资产内容放在一起，因此整个 `assets/` 目录拷走即可迁移；即使 CapNest 不存在，资产本身依然是可读、可拷贝、可复用的普通目录与文件。

## 资产与 Profile 的存储形态

| 对象 | 存储形态 | 描述文件 |
| --- | --- | --- |
| MCP Server | 目录 | 目录内的 `capability.yaml` + 原生 MCP 配置（如 `server.json`） |
| Skill | 目录 | 目录内的 `capability.yaml` + 原生 `SKILL.md` 及其附属文件 |
| Workflow | 目录 | 目录内的 `capability.yaml` + `workflow.yaml`（可附带脚本、模板） |
| Profile | 单个 YAML 文件 | `profiles/<name>.yaml`，锁文件为 `profiles/<name>.lock.yaml` |

三类能力统一为**目录**形态，好处是哈希、Diff、拷贝的规则完全一致：内容哈希对目录内文件做规范化计算后得到，不受文件数量影响。

Workflow 采用目录而非单个 YAML 文件，是为了与 Skill 保持一致——Workflow 后续很可能需要附带提示词片段、模板或脚本。

## 标识与命名

| 概念 | 规则 | 示例 |
| --- | --- | --- |
| 资产 ID | `<目录名>/<name>`，目录名 ∈ {`skills`、`mcp`、`workflows`} | `skills/sql-analysis` |
| Profile 名 | 单段小写标识 | `research` |
| Target 名 | Agent 稳定标识 | `codex`、`claude-code` |

两条必须分清的规则：

1. **资产 ID 的前缀是目录名**（`skills` / `mcp` / `workflows`），因为 ID 用于在磁盘上定位资产。
2. **Manifest 中的 `spec.type` 是协议类型名**（`skill` / `mcp-server` / `workflow`），因为它描述内容遵循哪套规范。

两套词表不通用，不要混用。Manifest 的 `components[].ref` 与依赖项一律引用**资产 ID 全名**。

资产目录名与资产 ID 的 `name` 部分保持一致，便于人工浏览与脚本推断。

## 版本与完整性

- 每个资产目录计算 **SHA256 内容哈希**，作为版本的物理依据。
- **语义版本** 写在 Manifest 中，由用户在 `capnest add` / `capnest bump` 时维护。
- 依赖解析结果写入 **Lockfile**，锁定依赖版本与哈希。
- 资产目录本身可用 Git 管理，Git commit 可作为版本的逻辑标识。

## Profile 结构（草案）

```yaml
apiVersion: capabilityhub.dev/v1alpha1
kind: CapabilityProfile

metadata:
  id: research
  name: Research
  version: 1.0.0

spec:
  components:
    - ref: skills/paper-review
    - ref: skills/research-assistant
    - ref: mcp/database

  targets:
    - codex
    - claude-code
```

Profile 只描述「要哪些能力、装到哪里」，具体版本由 Lockfile 决定。完整字段说明见 [`03-capability-manifest.md`](03-capability-manifest.md)。
