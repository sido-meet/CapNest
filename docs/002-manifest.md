# 002 Manifest

CapNest 不重新定义 Skill、MCP、Plugin 的内部格式，只提供一个统一的外层描述。

## 三种 kind

| kind | 放在哪 | 描述什么 | 例子 |
| --- | --- | --- | --- |
| `Capability` | 资产目录内的 `capability.yaml` | 一个具体资产：自己是什么、入口是什么、依赖什么 | `assets/skills/sql-analysis/capability.yaml` |
| `CapabilityProfile` | `profiles/<name>.yaml` | 一个能力组合：引用哪些资产、部署到哪些 Agent | `profiles/research.yaml` |
| `CapabilityLock` | `profiles/<name>.lock.yaml` | 组合的依赖解析结果，由 CapNest 生成，勿手改 | `profiles/research.lock.yaml` |

三者共用同一个 `apiVersion`。

**路径基准**：资产级 Manifest 位于资产目录内，因此 `entrypoint` 一律相对于该 Manifest 所在目录解析。Profile 是引用型的，不含任何 `entrypoint`。

## apiVersion

```
io.capnest.capability/v1alpha1
```

reverse-DNS 形式，与 Agent Skills（`agentskills.io`）、MCP Registry（`io.modelcontextprotocol.registry/…`）保持同一惯例。**命名空间在 v1 发布前定稿，之后 `apiVersion` 变更即属破坏性变更。**

## 资产级 Manifest

```yaml
apiVersion: io.capnest.capability/v1alpha1

kind: Capability

metadata:
  id: skills/sql-analysis
  name: SQL Analysis
  version: 1.0.0
  description: Analyze SQL queries and explain execution plans

spec:
  type: skill
  format: agentskills.io
  entrypoint: ./SKILL.md

  dependencies: []

  permissions:
    requested: []
```

一个 MCP Server：

```yaml
apiVersion: io.capnest.capability/v1alpha1

kind: Capability

metadata:
  id: mcp/database
  name: Database
  version: 1.0.0
  description: Query and inspect the local PostgreSQL database

spec:
  type: mcp-server
  format: mcp.local-config
  entrypoint: ./server.json

  dependencies: []

  permissions:
    requested:
      - database
```

一个 Workflow：

```yaml
apiVersion: io.capnest.capability/v1alpha1

kind: Capability

metadata:
  id: workflows/data-diagnosis
  name: Data Diagnosis
  version: 1.0.0
  description: Multi-step pipeline for diagnosing data quality issues

spec:
  type: workflow
  format: io.capnest.workflow/v1alpha1
  entrypoint: ./workflow.yaml

  dependencies:
    - ref: skills/sql-analysis
      version: ">=1.0.0 <2.0.0"

  permissions:
    requested:
      - database
```

### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `apiVersion` | 是 | Manifest 格式版本，用于向后兼容演进 |
| `kind` | 是 | `Capability` / `CapabilityProfile` / `CapabilityLock` |
| `metadata.id` | 是 | 资产 ID（`<目录名>/<name>`）或 Profile 名（单段标识） |
| `metadata.name` | 是 | 人类可读名称 |
| `metadata.version` | 是 | 语义版本 |
| `metadata.description` | 否 | 一句话说明 |
| `metadata.source` | 否 | 资产从哪来。本地创建的资产没有它；从 Agent 侧**收编**来的资产会带上 `target`（`mcode` / `claude-code`）与 `name`（在那边叫什么） |
| `metadata.sources` | 否 | 同一份能力在**多个** Agent 侧都有时，列出全部来源。`source` 始终等于第一个来源 |
| `spec.type` | 是（仅 `Capability`） | 协议类型：`skill` / `mcp-server` / `workflow` |
| `spec.format` | 是（仅 `Capability`） | 内容格式标识，原生格式用其规范名 |
| `spec.entrypoint` | 是（仅 `Capability`） | 入口文件，**相对于 Manifest 所在目录** |
| `spec.dependencies` | 否（仅 `Capability`） | 依赖列表，默认空列表 |
| `spec.permissions.requested` | 否 | 声明所需权限类别，供校验与提示 |
| `spec.deployment` | 否 | 部署形态与开关，见 [004 Deployment](004-deployment.md) |
| `spec.components[].ref` | 是（仅 `CapabilityProfile`） | 引用的资产 ID 全名 |
| `spec.components[].version` | 否（仅 `CapabilityProfile`） | 版本约束，省略表示沿用 Lockfile |
| `spec.targets` | 否（仅 `CapabilityProfile`） | 部署目标 Agent |

### 来源标记

从 Agent 侧收编来的资产，`metadata.source` 记录它是从哪收的：

```yaml
metadata:
  id: skills/doc-coauthoring
  name: doc-coauthoring
  version: 0.1.0
  description: ''
  source:
    target: claude-code
    name: doc-coauthoring
```

`list` 的 SOURCE 列直接读它；本地创建的资产没有这个字段，显示 `local`。

**来源标记里不记时间戳**：时间戳会进入内容哈希，让同一份来源两次收编得到两个哈希。CapNest 的哈希必须**可复现**——收编时间交给 git 版本历史去记。

同一份能力在两个 Agent 侧都有时，收编第二次**不会再复制一份**，
只会把第二个来源并进 `metadata.sources`：

```yaml
metadata:
  id: skills/doc-coauthoring
  name: doc-coauthoring
  version: 0.1.0
  source:
    target: mcode
    name: doc-coauthoring
  sources:
    - target: mcode
      name: doc-coauthoring
    - target: claude-code
      name: doc-coauthoring
```

### `spec.format` 词表

| 值 | 含义 | v1 支持 |
| --- | --- | --- |
| `agentskills.io` | Skill 原生格式 | 登记 + 部署 |
| `mcp.local-config` | **本地 MCP 启动配置**（`command`/`args`/`env` 或 `url`/`headers`） | 登记 + 部署 |
| `mcp.registry-server-json` | MCP Registry 的发布元数据（发行方式，不是启动方式） | 仅校验 |
| `codex.plugin` | `.codex-plugin/plugin.json` | 仅校验 |
| `claude.plugin` | `.claude-plugin/plugin.json` | 仅校验 |
| `io.capnest.workflow/v1alpha1` | Workflow 描述 | 登记，不部署 |

`mcp.registry-server-json` 与 `mcp.local-config` 必须分开：前者描述「这个 server 如何**发布**」（npm / pypi / docker 发行方式），后者描述「这个 server 如何**在本机启动**」。混用一个 format id 会让本地资产无法表达。

## Profile 级 Manifest

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

Profile 不含 `entrypoint` 与 `permissions`——这些属于单个资产。

## 依赖与 Lockfile

依赖条目：

```yaml
dependencies:
  - ref: skills/sql-analysis
    version: ">=1.2.0 <2.0.0"
    optional: false
```

解析结果写入与 Profile 同名的 `profiles/research.lock.yaml`：

```yaml
apiVersion: io.capnest.capability/v1alpha1

kind: CapabilityLock

metadata:
  id: research
  name: Research
  version: 1.0.0

spec:
  resolved:
    - ref: skills/paper-review
      version: 1.3.0
      hash: sha256:9f2c...
      source: local
    - ref: skills/research-assistant
      version: 1.0.0
      hash: sha256:41ab...
      source: local
    - ref: mcp/database
      version: 1.0.0
      hash: sha256:7de0...
      source: local
```

## 演进原则

- 字段只增不删，破坏性变更必须提升 `apiVersion` 主版本。
- 未知字段一律忽略（forward compatible）。
- `format` 使用「谁定义的格式就用谁的域名」规则，例如 `agentskills.io`、`mcp.local-config`。
- CapNest 私有格式统一使用 `io.capnest.*` 前缀。
- `spec.type`（协议类型名）与资产 ID 的目录名是两套词表，不要混用。

## 待决问题

- [ ] `permissions` 的权限类别词表
- [ ] Workflow 的 `workflow.yaml` 最小描述格式
- [ ] 是否支持更细粒度的 `compatibility`（如 `mcode@0.6`）

## 下一个

[003 Architecture](003-architecture.md) — 这些文件如何被代码读取、校验与存储。
