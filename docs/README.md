# CapNest 文档

本目录是 CapNest 的设计与实现文档，按编号顺序阅读，每篇只建立在它之前的内容之上。

文档描述**被构建的东西**。内容随实现进展修订，已实现的行为以代码为准。

## 阅读顺序

| # | 文档 | 回答的问题 |
| --- | --- | --- |
| 000 | [Philosophy](000-philosophy.md) | CapNest 是什么，不是什么 |
| 001 | [Domain model](001-domain.md) | 管理哪些资产，如何组织与标识 |
| 002 | [Manifest](002-manifest.md) | 统一的资产描述格式 |
| 003 | [Architecture](003-architecture.md) | 工程结构、模块职责、数据模型 |
| 004 | [Deployment](004-deployment.md) | 部署做了什么，安全规则是什么 |
| 005 | [Adapters](005-adapters.md) | 两个 Agent 的真实配置格式 |
| 006 | [CLI](006-cli.md) | 命令规格、输出协议、退出码 |
| 007 | [Tasks](007-tasks.md) | 先做什么，后做什么 |
| 008 | [Acceptance](008-acceptance.md) | 什么算做完了 |
| 009 | [Cookbook](009-cookbook.md) | 如何新增一个部署目标 |
| 010 | [Minimum implementation](010-minimal-implementation.md) | **第一刀：最小工程实现的方案与顺序** |

## 约定

| 术语 | 含义 |
| --- | --- |
| 能力（Capability） | 可被 Agent 复用的资产单元，泛指 MCP Server / Skill / Workflow |
| Profile | 多个能力的组合，是部署的单位 |
| Target | 部署目标 Agent，如 `mcode`、`claude-code` |
| Lockfile | 记录资产及其依赖的确切版本，保证跨 Agent 部署一致 |
| 漂移（drift） | Agent 侧配置被外部修改，与 CapNest 记录不一致 |
| 版本落后（version lag） | `assets/` 中的资产已更新，尚未重新部署 |

## 状态标记

任务清单用 Markdown checkbox 表示进度，与里程碑划分一一对应。

- [ ] 未开始
- [x] 已完成
- ⏳ 有阻塞