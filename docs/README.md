# CapNest 文档

本目录是 CapNest 的设计与规划文档集。文档以**提案（Proposal）**形式维护：内容会随实现进展被修订，已实现的行为以代码为准。

## 阅读顺序

| # | 文档 | 读者关心的问题 |
| --- | --- | --- |
| 01 | [产品定位](01-positioning.md) | CapNest 是什么、不是什么 |
| 02 | [核心资产模型](02-asset-model.md) | 我们管理哪些资产，如何组织 |
| 03 | [Capability Manifest](03-capability-manifest.md) | 统一的资产描述格式 |
| 04 | [MVP 定义](04-mvp.md) | 第一版做什么、怎么用 |
| 05 | [技术架构](05-architecture.md) | 用什么技术、怎么分层 |
| 06 | [开发路线](06-roadmap.md) | 分几步走、每步如何验收 |
| 07 | [验收标准](07-acceptance.md) | 什么算做完了 |
| 08 | [竞品策略](08-competitive.md) | 哪些不重复造轮子 |

## 约定

- **能力（Capability）**：可被 Agent 复用的资产单元，泛指 MCP Server / Skill / Workflow。
- **Profile**：多个能力的组合与分发单元。
- **Target**：能力的部署目标 Agent（如 `codex`、`claude-code`）。
- **Lockfile**：记录资产及其依赖的确切版本，保证跨 Agent 部署一致。
- **Drift（漂移）**：Agent 侧配置被外部修改，导致与 CapNest 记录不一致。

## 状态标记

文档中的任务清单使用 Markdown checkbox 表示进度，与 `docs/06-roadmap.md` 中的阶段划分一一对应。

- [ ] 未开始
- [x] 已完成
- ⚠️ 进行中或有阻塞
