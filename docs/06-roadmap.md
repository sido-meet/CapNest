# 06 · 开发路线规划

分五个阶段，每个阶段有独立验收标准。

## Phase 0：竞品验证与技术预研

**当前阶段。** 目标：避免重复造轮子。

- [ ] 安装 Microsoft APM，测试跨 Agent 部署
- [ ] 研究 AI Capability Registry 的目录设计
- [ ] 研究 Agent Plugins 规范
- [ ] 收敛 Manifest 最小字段（草案见 [`03-capability-manifest.md`](03-capability-manifest.md)，Phase 0 定稿）
- [ ] 收敛 Workflow 最小描述格式（同上）

**产出**：技术选型文档、Manifest 草案、竞品验证记录。

**验收**：能明确回答「APM 哪些能力可直接复用、哪些必须自建」。

## Phase 1：Local Registry

- [ ] 本地资产仓库
- [ ] MCP / Skill / Workflow 导入
- [ ] Manifest 解析和校验（资产级 `Capability` + Profile 级 `CapabilityProfile`）
- [ ] SQLite 元数据索引
- [ ] Profile 管理
- [ ] 基础版本和 Hash

**验收**：所有个人能力能够统一登记、搜索、组合。

**对应命令**：`init` `add` `list` `search` `validate` `profile create`

## Phase 2：Cross-Agent Deployment

- [ ] Codex Adapter
- [ ] Claude Code Adapter
- [ ] MCP 配置转换
- [ ] Skill 自动部署
- [ ] Lockfile
- [ ] Diff / Apply / Rollback
- [ ] Drift Detection

**验收**：同一 Profile 能够稳定部署到两个 Agent。

**对应命令**：`plan` `apply` `status` `rollback`

## Phase3：Agent Discovery

- [ ] CapNest MCP Server
- [ ] 搜索能力
- [ ] 查询能力详情
- [ ] 查看 Profile
- [ ] 查询部署状态
- [ ] 申请启用能力

**验收**：Codex、Claude Code 可以主动发现 CapNest 中的能力。

## Phase 4：产品化

- [ ] Tauri 桌面端
- [ ] 可视化资产管理
- [ ] 依赖关系图
- [ ] Skill Validator
- [ ] 更多 Agent Adapter
- [ ] 可选 Git 远程同步
- [ ] 能力分享与导入导出

**验收**：形成完整的个人本地能力管理产品。

## 阶段依赖关系

```
Phase 0 ──> Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 4
   │            │            │
  预研        资产层        部署层
```

Phase 0 的结论会直接改变 Phase 1/2 的实现范围，因此**不建议在 Phase 0 完成前开始编码**。

## 立即可做的三件事

1. 验证 APM，确定哪些基础能力直接复用
2. 定义 CapNest 的最小 Manifest 和资产目录
3. 用 Codex + Claude Code 跑通第一个跨 Agent 部署闭环

这三件事完成后，再进入正式开发。
