# 08 · 竞品策略

## 我们不重复开发什么

| 现有项目 | 我们的策略 |
| --- | --- |
| Microsoft APM | 优先复用其依赖解析、Lockfile、部署设计，评估是否直接集成 |
| Agent Skills | 直接兼容原生规范 |
| MCP Registry | 兼容其 Server 描述 |
| Agent Plugins | 兼容其插件包格式 |
| AI Capability Registry | 借鉴 Git-first 资产组织 |
| AionUi | 作为 Agent Workspace 和能力消费者，**不是部署目标**，CapNest 不向其写入配置 |
| Hermes Registry | 参考统一 Workflow Manifest |

## 核心原则

**CapNest 不应该为了证明自己有技术含量，重新实现 APM 已经解决的依赖管理。**

如果经过实验发现 APM 的能力可以直接复用，我们就把它作为底层 Package Manager，而 CapNest 专注于：

- 个人 Registry
- 资产组织
- Workflow 描述
- Agent Discovery

这会让项目更轻，也更有实际价值。

## 复用 vs 自建 判定表

Phase 0 调研时逐项填表：

| 能力 | 候选来源 | 自建成本 | 复用代价 | 结论 |
| --- | --- | --- | --- | --- |
| 依赖解析 | Microsoft APM | 中 | 需适配本地资产目录 | 待定 |
| Lockfile | Microsoft APM | 低 | 格式需与 Manifest 协同 | 待定 |
| Skill 格式 | Agent Skills | 零（直接兼容） | — | 直接兼容 |
| MCP Server 描述 | MCP Registry | 零（直接兼容） | — | 直接兼容 |
| 插件打包 | Agent Plugins | 低 | 与 Profile 概念重叠 | 待定 |
| 资产索引 | 自建（SQLite） | 低 | 无现成方案 | 自建 |
| Diff / Apply / Rollback | 自建 | 中 | APM 部分可借鉴 | 自建 |
| Discovery MCP Server | 自建 | 中 | 无现成方案 | 自建 |

## 评估 APM 的问题清单

- [ ] 是否支持「本地目录即资产源」的模型，还是强绑定 registry？
- [ ] Lockfile 是否可与我们的 Manifest 分离独立演进？
- [ ] 是否支持将产物分发到多个 Agent 的非标准目录？
- [ ] 部署前是否提供可读的 Diff？
- [ ] 是否有可靠的回滚语义？
- [ ] 作为库调用还是只能作为 CLI 调用？
- [ ] 许可证与项目是否兼容？

## 差异化定位

一句话总结 CapNest 与相邻产品的区别：

> APM 解决「一个包如何被安装」，CapNest 解决「我拥有的这些能力，如何被沉淀、组合、迁移和发现」。
