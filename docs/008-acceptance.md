# 008 Acceptance

第一个版本的成功定义成一个**具体场景**，而不是一份功能清单。

## 首个完整演示项目：Data Agent 能力组合

| 类别 | 内容 |
| --- | --- |
| MCP | Database MCP、Filesystem MCP |
| Skills | SQL Analysis、Data Diagnosis |
| Workflow | Data Diagnosis Pipeline |
| mcode | 可用 |
| Claude Code | 可用 |

## 通过标准

- [ ] 资产只维护一份
- [ ] 两个 Agent 都能正常使用对应 Skill 和 MCP
- [ ] 两个 Agent 部署的版本一致
- [ ] 修改资产后能够检测出**版本落后**
- [ ] 外部修改 Agent 配置后能够检测出**漂移**
- [ ] 更新前能够预览 Diff
- [ ] 出错后能够回滚
- [ ] 更换 Agent 不需要重新建设资产

## 验收执行方式

以脚本化的端到端流程执行，每条对应一次可复现的命令序列：

| 验收项 | 验证方式 |
| --- | --- |
| 资产只维护一份 | 删除 Agent 侧副本，从 `assets/` 重新部署，结果一致 |
| 两个 Agent 都可用 | 在 mcode 与 Claude Code 中各执行一次真实任务（如查询数据库并给出 SQL 分析结论） |
| 版本一致 | 比对两侧部署后的资产哈希 |
| 版本落后可检测 | 修改 `assets/` 中的 Skill，重跑 `status` 提示该资产版本落后 |
| 漂移可检测 | 手工改动 Agent 侧配置，重跑 `status` 报 drift |
| Diff 可预览 | `capnest plan` 输出 unified diff，且不改动任何文件 |
| 可回滚 | `capnest apply` 后执行 `capnest rollback`，断言配置回到初始状态 |
| 换 Agent 无需重建 | 在一个新 Agent 目标上部署同一 Profile |

「版本落后」与「漂移」是两种不同的检测，实现与验收都必须分开：前者比对资产哈希，后者比对目标配置哈希。详见 [004 Deployment](004-deployment.md)。

## 非功能性要求

| 项 | 要求 |
| --- | --- |
| 平台 | Windows 优先，路径处理与配置位置需在目标系统上验证 |
| 幂等性 | 同一 Profile 重复 `apply` 不产生额外变更 |
| 可逆性 | 任何 `apply` 都能通过 `rollback` 完全还原 |
| 性能 | 个人规模资产（数十个）下，`list` / `search` / `plan` 秒级响应 |
| 离线可用 | 核心流程不依赖网络 |

## 完成定义（DoD）

一个里程碑的任务全部勾选、验收项全部通过、且对应文档更新完毕，才算该里程碑完成。