# SETUP

本文是安装 CapNest 的操作手册。步骤较多，建议让一个 coding agent 读着它与你一起完成：

> 读一下本仓库的 SETUP.md，和我一起把 CapNest 装好。

## 当前状态

仓库处于**实现阶段**：M0 工程地基已落地，§2 的命令正在随里程碑逐步可用。当前可用的命令是 `init` 与 `doctor`；`add` / `list` / `search` / `validate` / `profile` 在 M1 之后可用，`plan` / `apply` / `status` / `rollback` 在 M2 之后可用。逐条进度见 [007 Tasks](docs/007-tasks.md)。

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

### 1.2 取代码

```powershell
git clone https://github.com/sido-meet/CapNest.git
cd CapNest
```

### 1.3 安装依赖

```powershell
uv sync
```

`uv sync` 会创建 `.venv` 并按 `uv.lock` 锁定依赖。

### 1.4 校验安装

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
├── assets/
│   ├── mcp/
│   ├── skills/
│   └── workflows/
├── profiles/
├── state/
│   ├── deployments.json
│   ├── ownership.json
│   ├── backups/
│   └── logs/
└── config.yaml
```

后续命令都要指明工作区。全局选项放在子命令之前：`capnest --workspace .\workspace <命令>`。工作区解析规则见 [006 CLI](docs/006-cli.md) 的「工作区解析」。

### 2.2 自检

```powershell
uv run capnest --workspace .\workspace doctor
```

`doctor` 只读不写：检查 Python 版本、工作区结构、各 target 的配置文件是否存在、Agent CLI 版本与版本号、每个 target 的能力矩阵、以及当前系统是否支持 `symlink` 部署形态。

### 2.3 登记能力

```powershell
uv run capnest --workspace .\workspace add skill   .\my-skills\sql-analysis
uv run capnest --workspace .\workspace add mcp     .\my-mcps\database
uv run capnest --workspace .\workspace add workflow .\my-workflows\data-diagnosis

# 从 mcode 侧收编既有 skill，原文件保持不动
uv run capnest --workspace .\workspace add --from mcode:manim
```

登记前会做隐藏 Unicode 扫描，命中即阻断。

### 2.4 组合与锁定

```powershell
uv run capnest --workspace .\workspace profile create data-agent --asset skills/sql-analysis --target mcode --target claude-code
```

`profile create` 生成 `profiles/data-agent.yaml`；也可以手工编辑它填入 `spec.components`。然后校验：

```powershell
uv run capnest --workspace .\workspace validate
```

### 2.5 预览部署

```powershell
uv run capnest --workspace .\workspace plan --profile data-agent --target mcode,claude-code
```

`plan` 是只读的，不写任何文件。

### 2.6 应用与验证

```powershell
uv run capnest --workspace .\workspace apply --profile data-agent --target mcode,claude-code
uv run capnest --workspace .\workspace status
```

### 2.7 回滚

```powershell
uv run capnest --workspace .\workspace rollback --target mcode
```

## 3. 让 Agent 帮你完成

`capnest` 的 `--json` 输出是一份稳定协议，GUI 与 Agent 都依赖它。因此可以直接让 Agent 操作：

> 用 `capnest --json` 把我的 `sql-analysis` skill 部署到 mcode 和 Claude Code，先给我看 plan。

`--json` 的字段约定见 [006 CLI](docs/006-cli.md)。
