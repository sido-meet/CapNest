# 03 · 统一 Capability Manifest

这是 CapNest 最值得长期建设的基础。

我们**不重新定义** Skill、MCP 的内部格式，而是提供一个统一的外层描述。

## 两种 kind

CapNest 有两类 Manifest，共用同一个 `apiVersion`：

| kind | 放在哪 | 描述什么 | 例子 |
| --- | --- | --- | --- |
| `Capability` | 资产目录内的 `capability.yaml` | 一个具体资产：自己是什么、入口文件是什么、依赖什么 | `assets/skills/sql-analysis/capability.yaml` |
| `CapabilityProfile` | `profiles/<name>.yaml` | 一个能力组合：引用哪些资产、部署到哪些 Agent | `profiles/research.yaml` |
| `CapabilityLock` | `profiles/<name>.lock.yaml` | 组合的依赖解析结果（由 CapNest 生成，勿手改） | `profiles/research.lock.yaml` |

**路径基准**：资产级 Manifest 位于资产目录内，因此 `entrypoint` 一律相对于该 Manifest 所在目录解析。Profile 是引用型的，不含任何 `entrypoint`。

## 资产级 Manifest 草案

> 这不是已发布的行业标准，是 CapNest 的设计草案。`apiVersion` 使用自有域名 `capabilityhub.dev` 占位，落地前需确认命名空间归属。

```yaml
apiVersion: capabilityhub.dev/v1alpha1

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

一个 MCP Server 资产的 Manifest：

```yaml
apiVersion: capabilityhub.dev/v1alpha1

kind: Capability

metadata:
  id: mcp/database
  name: Database
  version: 1.0.0
  description: Query and inspect the local PostgreSQL database

spec:
  type: mcp-server
  format: mcp.server-json
  entrypoint: ./server.json

  dependencies: []

  permissions:
    requested:
      - database
```

一个 Workflow 资产的 Manifest：

```yaml
apiVersion: capabilityhub.dev/v1alpha1

kind: Capability

metadata:
  id: workflows/data-diagnosis
  name: Data Diagnosis
  version: 1.0.0
  description: Multi-step pipeline for diagnosing data quality issues

spec:
  type: workflow
  format: capabilityhub.workflow/v1alpha1
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
| `spec.type` | 是（仅 `Capability`） | 协议类型：`skill` / `mcp-server` / `workflow` |
| `spec.format` | 是（仅 `Capability`） | 内容格式标识，原生格式用其规范名 |
| `spec.entrypoint` | 是（仅 `Capability`） | 入口文件，**相对于 Manifest 所在目录** |
| `spec.dependencies` | 是（仅 `Capability`） | 依赖列表（见下） |
| `spec.permissions.requested` | 否 | 声明所需权限类别，供校验与提示 |
| `spec.components[].ref` | 是（仅 `CapabilityProfile`） | 引用的资产 ID 全名 |
| `spec.components[].version` | 否（仅 `CapabilityProfile`） | 版本约束，省略表示沿用 Lockfile |
| `spec.targets` | 否（仅 `CapabilityProfile`） | 部署目标 Agent |

## Profile 级 Manifest 草案

```yaml
apiVersion: capabilityhub.dev/v1alpha1

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
    - codex
    - claude-code
```

Profile 不含 `entrypoint` 与 `permissions`——这些属于单个资产。**Profile 是部署的单位**，因此 Lockfile、Diff、Apply、Rollback 全部以 Profile 为粒度。

## 依赖与 Lockfile

依赖条目草案（资产级与 Profile 级通用）：

```yaml
dependencies:
  - ref: skills/sql-analysis
    version: ">=1.2.0 <2.0.0"
    optional: false
```

解析结果写入与 Profile 同名的 `profiles/research.lock.yaml`：

```yaml
apiVersion: capabilityhub.dev/v1alpha1

kind: CapabilityLock

metadata:
  id: research
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

Lockfile 的作用是保证 **Codex 与 Claude Code 部署的是完全相同版本的能力**。

## 参考的现有规范

| 规范 / 项目 | 我们借鉴什么 |
| --- | --- |
| Agent Skills | Skill 原生格式 |
| MCP Registry | MCP Server 描述 |
| Agent Plugins | MCP + Skill 打包 |
| Microsoft APM | 依赖管理、Lockfile、跨 Agent 部署 |
| Hermes Registry | 统一 Manifest 和 Workflow 描述 |

## 演进原则

- 字段只增不删，破坏性变更必须提升 `apiVersion` 主版本。
- 未知字段一律忽略（forward compatible）。
- `format` 使用「谁定义的格式就用谁的域名」规则，例如 `agentskills.io`、`mcp.server-json`。
- CapNest 私有格式统一使用 `capabilityhub.*` 前缀。
- `spec.type`（协议类型名）与资产 ID 的目录名是两套词表，不要混用。

## 待决问题

- [ ] 命名空间 `capabilityhub.dev` 是否最终采用（域名未注册前可先用 `capnest.dev`）
- [ ] `permissions` 的权限类别词表
- [ ] Workflow 的 `workflow.yaml` 最小描述格式
- [ ] 是否支持更细粒度的 `compatibility`（如 `codex@0.9`）
