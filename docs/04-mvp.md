# 04 · MVP 定义

## MVP 核心目标

**创建一份能力资产，在一个地方维护，让 Codex 和 Claude Code 都能够使用，而且版本保持一致。**

MVP 是一个完整、可验证的能力资产管理闭环，而不是一个功能很多的桌面软件。

## 功能范围

| 模块 | 功能 | 优先级 |
| --- | --- | --- |
| Asset Registry | MCP / Skill / Workflow 导入 | P0 |
| Manifest | 统一资产描述 | P0 |
| Asset Manager | 搜索、分类、元数据管理 | P0 |
| Profile | 组合多个能力 | P0 |
| Version Manager | 版本、Hash、Lockfile | P0 |
| Codex Adapter | Skill / MCP 部署 | P0 |
| Claude Adapter | Skill / MCP 部署 | P0 |
| Deployment | Diff、Apply、Backup、Rollback | P0 |
| Validator | Manifest、依赖和路径检查 | P1 |
| MCP Discovery | Agent 搜索和查询能力 | P1 |
| GUI | 桌面管理界面 | P2 |
| Marketplace | 公共资产市场 | 暂不开发 |

## 完整使用场景

假设你已经拥有：

- 3 个 MCP Server：QQ、KeePassXC、Database
- 3 个 Skill：Paper Review、SQL Analysis、Research Assistant
- 1 个 Workflow：Data Diagnosis

你创建一个 Research Profile（`profiles/research.yaml`）：

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

然后执行：

1. **导入资产** — 把现有 Skill 和 MCP 注册到 CapNest
2. **创建 Profile** — 组合需要的能力
3. **解析依赖** — 检查版本、依赖和兼容性，生成 Lockfile
4. **部署预览** — 计算 Codex 和 Claude Code 需要修改的配置，展示 Diff
5. **执行部署** — 备份原配置，应用修改
6. **检查结果** — 验证两个 Agent 都能发现并使用这些能力
7. **更新和回滚** — 修改资产后同步更新，发生问题可以恢复

## CLI 命令设计

第一版不急着开发 GUI，先把核心 CLI 做好。

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

### 命令语义约定

| 命令 | 是否修改状态 | 说明 |
| --- | --- | --- |
| `init` | 是 | 创建资产目录骨架与 `config.yaml` |
| `add` | 是 | 复制或引用资产到 `assets/`，生成资产级 `capability.yaml` 与哈希 |
| `list` / `search` | 否 | 读取 SQLite 索引与 Manifest |
| `validate` | 否 | 仅校验，不写入 |
| `profile create` | 是 | 生成 `profiles/<name>.yaml`（`kind: CapabilityProfile`） |
| `plan` | 否 | 计算并展示 Diff，不落盘。接受 `--profile` / `--target` |
| `apply` | 是 | 备份 → 应用 → 记录部署状态。接受与 `plan` 完全相同的 `--profile` / `--target` |
| `status` | 否 | 展示各 Target 的部署版本与漂移状态 |
| `rollback` | 是 | 从 `state/backups/` 恢复上次部署前的配置 |

**`plan` 与 `apply` 必须共用同一套 diff 计算逻辑**，保证预览与实际执行一致。因此：

- `apply` 必须接受与 `plan` 完全相同的 `--profile` / `--target` 取值；两者都允许省略，回落到 `config.yaml` 中的默认 Profile 与默认 Target。
- `apply` 必须能复现最近一次 `plan` 的作用范围，否则拒绝执行并提示重新 `plan`。

## 首期不做

- 桌面 GUI
- 公共 Marketplace
- Workflow 执行引擎
- 远程同步与账号体系
- 完整的语义化版本冲突解决（先以 Lockfile 固定为主）
