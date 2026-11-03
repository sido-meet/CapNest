# SETUP

本文是安装 CapNest 的操作手册。步骤较多，建议让一个 coding agent 读着它与你一起完成：

> 读一下本仓库的 SETUP.md，和我一起把 CapNest 装好。

## 当前状态

仓库处于**设计阶段**。本文分两部分：

- **§1 现在就能做的**：环境准备与工作区准备，实现就绪后即可继续。
- **§2 实现就绪后的流程**：完整的初始化、登记、部署与验证闭环。标 ⏳ 的步骤在实现落地前不可执行。

## 1. 环境准备

### 1.1 依赖

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| Python | 3.11+ | 运行时 |
| [uv](https://docs.astral.sh/uv/) | 0.11+ | 依赖与虚拟环境管理 |
| git | 任意 | 资产目录建议纳入版本控制 |
| node | 20+ | 仅当资产依赖 npx 启动的 MCP Server |

Windows 上安装 `uv`：

```powershell
winget install --id=astral-sh.uv -e
```

### 1.2 取代码并安装依赖

```powershell
git clone https://github.com/sido-meet/CapNest.git
cd CapNest
uv sync
```

`uv sync` 会创建 `.venv` 并按 `pyproject.toml` 锁定依赖。

### 1.3 校验安装

```powershell
uv run capnest --version
```

## 2. 实现就绪后的流程

### 2.1 初始化工作区

工作区是 CapNest 的根目录，存放资产、Profile 与状态。

```powershell
uv run capnest init .\workspace
```

生成的结构：

```
workspace/
├── assets/{mcp,skills,workflows}/
├── profiles/
├── state/{backups,deployments,logs}/
└── config.yaml
```

### 2.2 自检

```powershell
uv run capnest doctor
```

`doctor` 只读不写：检查 Python 版本、工作区结构、各 target 的配置文件是否存在、Agent CLI 版本与版本号、每个 target 的能力矩阵、以及当前系统是否支持 `symlink` 部署形态。

### 2.3 登记能力

```powershell
uv run capnest add skill   .\my-skills\sql-analysis
uv run capnest add mcp     .\my-mcps\database
uv run capnest add workflow .\my-workflows\data-diagnosis

# 从 Codex 侧收编既有 skill，原文件保持不动
uv run capnest add --from codex:paper-write-skill
```

登记前会做隐藏 Unicode 扫描，命中即阻断。

### 2.4 组合与锁定

```powershell
uv run capnest profile create data-agent --target codex --target claude-code
```

编辑 `profiles/data-agent.yaml` 填入 `spec.components`，然后校验：

```powershell
uv run capnest validate
```

### 2.5 预览部署

```powershell
uv run capnest plan --profile data-agent --target codex,claude-code
```

`plan` 是只读的，不写任何文件。

### 2.6 应用与验证

```powershell
uv run capnest apply --profile data-agent --target codex,claude-code
uv run capnest status
```

### 2.7 回滚

```powershell
uv run capnest rollback --target codex
```

## 3. 让 Agent 帮你完成

`capnest` 的 `--json` 输出是一份稳定协议，GUI 与 Agent 都依赖它。因此可以直接让 Agent 操作：

> 用 `capnest --json` 把我的 `sql-analysis` skill 部署到 Codex 和 Claude Code，先给我看 plan。

`--json` 的字段约定见 [006 CLI](docs/006-cli.md)。