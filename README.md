# CapNest

**Personal Capability Infrastructure**

个人积累的 AI 能力（MCP Server / Skill / Workflow）独立于 Agent 存在，以版本化的 Profile 组合，一次部署到多个 Agent，得到**完全相同的一份能力**。

> 当前处于设计阶段：文档先行，实现按 [任务清单](docs/007-tasks.md) 逐条推进。

## Setup

安装与上手见 [SETUP.md](SETUP.md)。步骤较多，因此由一个 coding agent 与你一起完成：

> 读一下本仓库的 SETUP.md，和我一起把 CapNest 装好。

## Documentation

按编号顺序阅读；每篇只建立在它之前的内容之上。

- [000 Philosophy](docs/000-philosophy.md)：CapNest 解决什么问题，边界在哪里
- [001 Domain model](docs/001-domain.md)：三种能力与一种组合，资产如何组织
- [002 Manifest](docs/002-manifest.md)：统一的资产描述格式
- [003 Architecture](docs/003-architecture.md)：工程结构、模块职责、数据模型
- [004 Deployment](docs/004-deployment.md)：部署语义、安全规则与状态
- [005 Adapters](docs/005-adapters.md)：两个目标 Agent 的真实配置格式
- [006 CLI](docs/006-cli.md)：命令规格、`--json` 协议与退出码
- [007 Tasks](docs/007-tasks.md)：逐条任务清单
- [008 Acceptance](docs/008-acceptance.md)：什么算做完了
- [009 Cookbook](docs/009-cookbook.md)：如何新增一个部署目标

## Development

`uv sync` 安装依赖；`uv run pytest` 跑测试，`uv run ruff check` 跑检查。任务编号与提交的对应见 [007 Tasks](docs/007-tasks.md)。

## License

[MIT](LICENSE)