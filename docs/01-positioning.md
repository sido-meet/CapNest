# 01 · 产品定位

## 我们要解决什么问题

现在每个 Agent 都有自己的 Skill、MCP、Plugin 和配置管理机制：

- Codex 有自己的 Skills 和 MCP 配置
- Claude Code 有自己的 Skills 和 MCP 配置
- OpenClaw 有自己的 Skills 和工具体系

用户在不同 Agent 中重复配置、复制和维护自己的能力。这是**能力归属错位**：能力本属于用户，却被托管在某个 Agent 的配置目录里。

**CapNest 要做的是：把个人积累的 AI 能力从 Agent 中解耦出来，形成独立的、可持续积累的资产。**

## 与其他产品的边界

| 产品 | 核心定位 | 负责什么 | 与 CapNest 的关系 |
| --- | --- | --- | --- |
| Codex | Agent Runtime | 规划、编码、执行 | 部署目标 |
| Claude Code | Agent Runtime | 规划、编码、执行 | 部署目标 |
| AionUi | Agent Workspace | 使用 Agent、会话管理、任务协作 | 上层消费者，**不是部署目标**，通过 Discovery 接口获取能力 |
| Microsoft APM | Agent Package Manager | 能力依赖、版本、安装和分发 | 优先复用其依赖管理 |
| **CapNest** | **Personal Capability Registry** | **能力沉淀、组织、组合、发现和跨 Agent 管理** | — |

我们不重新开发 Agent，我们关注的是它们**之下的公共能力资产层**。

## 四个核心价值

### 1. Capability Persistence

能力独立存储，不依附于某个 Agent。更换 Agent 不需要重新建设。

### 2. Capability Composition

MCP、Skill、Workflow 可以组合成 Profile，形成可复用的能力集合。

### 3. Capability Portability

一份资产适配多个 Agent，统一管理版本、依赖、部署和回滚。

### 4. Capability Discovery

Agent 可以通过 MCP 搜索、查询、了解和申请使用已有能力。

## 目标用户

第一阶段只有一个用户画像：**同时使用多个 Agent 的重度 AI 用户**。典型场景是白天用 Codex 写代码，晚上用 Claude Code 做论文调研，两边都需要同一套「SQL 分析」「数据库 MCP」「论文评审」能力。

这类用户的痛点不是「没有能力」，而是**能力无法沉淀、无法迁移、无法保持版本一致**。

## 非目标

明确不做的事，避免项目膨胀：

- 不做通用 Agent Runtime
- 不做 Agent Workspace / 会话管理
- 不做公共 Marketplace（远期）
- 不做 Workflow 执行引擎（首期）
- 不重造 Skill / MCP 的原生格式
- 不实现通用包管理器（优先复用 APM）
