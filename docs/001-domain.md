# 001 Domain model

本文命名 CapNest 的概念及其约束。代码、CLI、Adapter 与后续文档只使用这些术语。

## 三种能力与一种组合

| 类型 | 定义 | 示例 | 原生规范 |
| --- | --- | --- | --- |
| MCP Server | 提供工具与数据访问 | QQ、Database、KeePassXC | MCP |
| Skill | 提供完成任务的方法与知识 | SQL Analysis、Paper Review | Agent Skills |
| Workflow | 描述多步骤任务流程 | Literature Review Pipeline | CapNest 自定义 |
| Profile | 组合多种能力，是部署的单位 | Research、Data Agent | CapNest 自定义 |

- **Skill** 遵循 Agent Skills 原生规范，CapNest 只做登记与分发。
- **MCP Server** 遵循 MCP 原生规范，CapNest 只做登记与分发。
- **Workflow** 首期只定义描述与依赖，不开发执行引擎，因此**只登记、不部署**。
- **Profile** 是部署单位，Lockfile、Diff、Apply、Rollback 全部以 Profile 为粒度。

### 粒度：只登记可独立安装的那一层

资产模型只覆盖「可独立安装、可独立版本化」的那一层，更细的粒度不单独建模。

| 层级 | 是否建模 | 原因 |
| --- | --- | --- |
| MCP Server | 是 | 独立可安装，有独立版本 |
| └─ Tool | 否 | 由 Server 在运行时注册，名字随 Server 版本变化，不稳定 |
| Skill | 是 | 独立可安装的目录 |
| └─ Skill 内部文件 | 否 | 是 Skill 的组成部分，不是独立资产 |
| Workflow | 是 | 独立可安装的目录 |

两个直接后果：

1. 登记一个 MCP Server 即获得它暴露的全部 Tool，**不需要枚举 Tool**。
2. Tool 名不是稳定标识，不能作为资产主键。`mcp__<server>__<tool>` 中的 server 别名与 tool 注册名两层都会变。

Skill 与 Tool 也在不同层：Skill 是给模型看的方法与知识，以文档形式注入上下文；Tool 是可调用的函数。Skill **引用** Tool，而不是包含 Tool。

### Profile 不是 Bundle

早期草案中 Profile 与 Bundle 两个组合概念职责重叠。本版**只保留 Profile** 作为组合与部署单位；「Bundle」一词只作为口语说法使用，不对应独立的 Manifest `kind`。

## 资产存储形态

三类能力统一为**目录**形态，好处是哈希、Diff、拷贝规则完全一致：内容哈希对目录内文件做规范化计算后得到，不受文件数量影响。

| 对象 | 存储形态 | 描述文件 |
| --- | --- | --- |
| MCP Server | 目录 | `capability.yaml` + 原生 MCP 启动配置（如 `server.json`） |
| Skill | 目录 | `capability.yaml` + 原生 `SKILL.md` 及附属文件 |
| Workflow | 目录 | `capability.yaml` + `workflow.yaml`（可附带脚本、模板） |
| Profile | 单个 YAML 文件 | `profiles/<name>.yaml`，锁文件 `profiles/<name>.lock.yaml` |

Workflow 采用目录而非单个 YAML，是为了与 Skill 保持一致——Workflow 后续很可能需要附带提示词片段、模板或脚本。

## 目录布局

文件系统是唯一事实来源。

```
CapNest/
├── assets/
│   ├── mcp/
│   │   ├── qq/
│   │   │   ├── capability.yaml      ← kind: Capability
│   │   │   └── server.json
│   │   └── database/
│   ├── skills/
│   │   ├── paper-review/
│   │   │   ├── capability.yaml      ← kind: Capability
│   │   │   └── SKILL.md
│   │   └── sql-analysis/
│   └── workflows/
│       └── data-diagnosis/
│           ├── capability.yaml      ← kind: Capability
│           └── workflow.yaml
├── profiles/
│   ├── research.yaml                ← kind: CapabilityProfile
│   ├── research.lock.yaml           ← kind: CapabilityLock
│   └── data-agent.yaml
├── state/
│   ├── deployments.json             # 部署记录
│   ├── ownership.json               # 路径 → 指纹
│   ├── backups/<timestamp>/         # 部署前的目标备份
│   └── logs/
└── config.yaml
```

| 目录 | 内容 | 纳入版本控制 |
| --- | --- | --- |
| `assets/` | 真正的能力内容，每个资产目录自带 `capability.yaml` | 建议 |
| `profiles/` | 能力组合定义及其锁文件 | 建议 |
| `state/` | 部署状态、归属声明、备份、日志 | 忽略 |
| `config.yaml` | CapNest 自身配置 | 建议 |

**`assets/` 必须可以脱离 CapNest 独立使用。** 资产描述与资产内容放在一起，整个目录拷走即可迁移；即使 CapNest 不存在，资产本身依然是可读、可拷贝、可复用的普通目录与文件。

## 标识与命名

| 概念 | 规则 | 示例 |
| --- | --- | --- |
| 资产 ID | `<目录名>/<name>`，目录名 ∈ {`skills`、`mcp`、`workflows`} | `skills/sql-analysis` |
| Profile 名 | 单段小写标识 | `research` |
| Target 名 | Agent 稳定标识 | `mcode`、`claude-code` |

两条必须分清的规则：

1. **资产 ID 的前缀是目录名**，因为 ID 用于在磁盘上定位资产。
2. **Manifest 中的 `spec.type` 是协议类型名**（`skill` / `mcp-server` / `workflow`），因为它描述内容遵循哪套规范。

两套词表不通用，不要混用。Manifest 的 `components[].ref` 与依赖项一律引用**资产 ID 全名**。

资产目录名与资产 ID 的 `name` 部分保持一致，便于人工浏览与脚本推断。

## 版本与完整性

- 每个资产目录计算 **SHA256 内容哈希**，作为版本的物理依据。规范化规则见 [003 Architecture](003-architecture.md)。
- **语义版本**写在 Manifest 中，由 `capnest add` / `capnest bump` 维护。
- 依赖解析结果写入 **Lockfile**，锁定各资产的版本与哈希。
- 资产目录可用 Git 管理，Git commit 可作为版本的逻辑标识。

Lockfile 的作用是保证 **mcode 与 Claude Code 部署的是完全相同版本的能力**。

## Profile 结构

```yaml
apiVersion: io.capnest.capability/v1alpha1
kind: CapabilityProfile

metadata:
  id: research
  name: Research
  version: 1.0.0
  description: Paper review and database research capabilities

spec:
  components:
    - ref: skills/paper-review
    - ref: skills/research-assistant
    - ref: mcp/database

  targets:
    - mcode
    - claude-code
```

Profile 只描述「要哪些能力、装到哪里」，具体版本由 Lockfile 决定。字段的完整说明见 [002 Manifest](002-manifest.md)。

## 下一个

[002 Manifest](002-manifest.md) — 这些概念如何被写成文件。