# CapNest

**Personal Capability Infrastructure**

个人积累的 AI 能力（MCP Server / Skill / Workflow）独立于 Agent 存在，以版本化的 Profile 组合，一次部署到多个 Agent，得到**完全相同的一份能力**。

> 当前处于实现阶段：M0 工程地基、M1 资产层、M2 部署层已落地，
> M3 的「统一管理」这条线（收编 → 去重 → 冲突 → 同步）已可用。

## 真实场景：把两个 Agent 的 skill 收成一份

```powershell
uv run capnest init .\workspace

# 1. 看看两个 Agent 侧现在各有什么
uv run capnest inspect claude-code
uv run capnest inspect mcode

# 2. 全部收编进工作区（同名同内容自动去重，同名不同内容记成冲突）
uv run capnest --workspace .\workspace add --from '*'

# 3. 看重复、看分歧
uv run capnest --workspace .\workspace dedupe
uv run capnest --workspace .\workspace conflict list

# 4. 裁掉分歧：以工作区为准 / 以目标为准
uv run capnest --workspace .\workspace conflict resolve skills/docx --use workspace --target mcode

# 5. 同步回两边（改一处 → 两边一致）
uv run capnest --workspace .\workspace sync --yes
uv run capnest --workspace .\workspace status
```

## Quick start

```powershell
uv sync
uv run capnest init .\workspace
uv run capnest --workspace .\workspace doctor
uv run capnest --workspace .\workspace add skill examples\data-agent\assets\skills\sql-analysis
uv run capnest --workspace .\workspace list
uv run capnest --workspace .\workspace profile create data-agent --asset skills/sql-analysis
uv run capnest --workspace .\workspace plan   --profile data-agent --target mcode,claude-code
uv run capnest --workspace .\workspace apply  --profile data-agent --target mcode,claude-code --yes
uv run capnest --workspace .\workspace status
uv run capnest --workspace .\workspace rollback --target mcode
```

全局选项放在子命令之前（`capnest --workspace ./ws --json <命令>`）。完整命令规格见 [006 CLI](docs/006-cli.md)。

想看目标 Agent 侧现在有哪些 skill：

```powershell
uv run capnest inspect claude-code
uv run capnest inspect mcode
```

想一次把目标侧的 skill 全收进工作区（`list` 的 SOURCE 列会显示 `Claude Code`）：

```powershell
uv run capnest --workspace .\workspace add --from claude-code:*
uv run capnest --workspace .\workspace list
uv run capnest --workspace .\workspace list --source "Claude Code"
```

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
- [010 Minimum implementation](docs/010-minimal-implementation.md)：**第一个能跑的东西长什么样**

## Development

`uv sync` 安装依赖；`uv run pytest` 跑测试，`uv run ruff check` 跑检查。任务编号与提交的对应见 [007 Tasks](docs/007-tasks.md)。

## License

[MIT](LICENSE)
