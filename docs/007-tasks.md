# 007 Tasks

本文是第一版的实施总纲与可执行任务清单。

**第一刀（最小工程实现）的具体方案与十步顺序见 [010 Minimum implementation](010-minimal-implementation.md)**——那是真正要先动手的部分，本文是它的完整版背景。

## 第一版要解决的问题

第一版不是「功能多一点的 Alpha」，而是**一个具体问题被完整解决**：

> 我在 mcode 和 Claude Code 之间来回用，同一套 Skill 和 MCP Server 却要维护两份。CapNest 让这两份变成一份：改一处、两边同步；同步前能看到差异；出了问题能一键还原。

**完成的标志**：一个 Profile 部署到两个 Agent，两边能力一致；改资产 → 看到 diff → 应用 → 两边同步；出问题 → 回滚还原。每一步都能独立验证。

## 最小化的四条准则

第一版的每个设计决策都受这四条约束。**凡是不服务于「解决上面那个问题」的功能，一律推到 v0.2 及以后。**

| 准则 | 含义 | 体现 |
| --- | --- | --- |
| **砍功能，不砍闭环** | 功能少可以，链路必须完整 | 导入 → 组合 → 预览 → 应用 → 检查 → 回滚，六步一个都不能断 |
| **砍自动化，不砍可验证性** | 不做智能决策，但每一步都能人工确认 | 不自动选版本，但每个决策都能 `plan` 出来看 |
| **砍存储，不砍正确性** | 不引入数据库，用文件 | 状态用 JSON 文件，索引直接扫目录 |
| **砍范围，不砍边界** | 只支持少数目标，但每个都做对 | 只做 mcode + Claude Code，但配置读写做到无损 round-trip |

## 里程碑与排序

五个里程碑，**严格串行**。每个里程碑结束时 `main` 必须可运行、能通过验收命令。

```
M0 工程地基 + Adapter 实测
   │
   ▼
M1 资产层        ← 导入（含收编）、检索、校验、组合、安全扫描
   │
   ▼
M2 部署层        ← 归属证明 / 原子写 / plan / apply / status / rollback / doctor
   │
   ▼
M3 闭环加固      ← 漂移、版本落后、幂等、往返测试、golden fixture
   │
   ▼
M4 收尾          ← 文档对齐、CI、打包
```

### M0 · 工程地基

**目标**：一个能跑的 `capnest` 命令、一份确定的工作区布局、以及一项 Adapter 实测。

**范围**：项目骨架、依赖管理、配置定位、`init`、`--json` 全局输出通道、错误体系与退出码、`doctor` 骨架；以及 [005 Adapters](005-adapters.md) 末尾的 skills 落点与配置目录实测。

**不做**：任何资产、Profile、部署逻辑。

**为什么实测放在 M0**：M2 是整个项目风险最高的部分（两个 Agent 的配置格式能不能无损读写）。实测结果如果与预期不符，M1 的 Manifest 设计要跟着改——所以必须早。

**验收**：

```bash
uv run capnest --version
uv run capnest --json init ./workspace
uv run capnest --workspace ./workspace doctor --json
```

### M1 · 资产层

**目标**：能力资产集中在一处，能导入、能收编、能找到、能校验、能组合。

**范围**：数据模型、目录规范化哈希、资产仓库、Profile、隐藏 Unicode 扫描、六个命令（`init` `add` `list` `search` `validate` `profile`）。

**不做**：任何与 Agent 相关的写操作。

**验收**：

```bash
uv run capnest --workspace ./workspace add skill examples/data-agent/assets/skills/sql-analysis
uv run capnest --workspace ./workspace add --from mcode:manim          # 收编既有资产
uv run capnest --workspace ./workspace list --json
uv run capnest --workspace ./workspace search "SQL"
uv run capnest --workspace ./workspace validate                        # 退出码 0
uv run capnest --workspace ./workspace profile create data-agent --asset skills/sql-analysis
```

`add mcp` 与 `add workflow` 的命令面已在 M1 实现（同一套资产仓库），但**演示资产**随第二刀的 MCP 一起补——第一刀不部署 MCP，也就没有可演示的 MCP 资产。

### M2 · 部署层

**目标**：把 Profile 部署到 mcode 和 Claude Code，可预览、可应用、可回滚。

**范围**：解析器、Diff 引擎、归属证明、原子写与预写事务、备份与回滚、部署状态、两个 Adapter、五个命令（`plan` `apply` `status` `rollback` `doctor`）。

**验收**：

```bash
uv run capnest --workspace ./workspace plan   --profile data-agent --target mcode,claude-code
uv run capnest --workspace ./workspace apply  --profile data-agent --target mcode,claude-code
uv run capnest --workspace ./workspace status --json
uv run capnest --workspace ./workspace rollback --target mcode
```

### M3 · 闭环加固

**目标**：这套东西可信。改资产能发现、外面改能发现、能还原、能重复执行。

**范围**：漂移检测、版本落后检测、幂等性、Apply→Rollback 往返测试、Adapter 的 golden fixture 测试。

**验收**：[008 Acceptance](008-acceptance.md) 的八条标准逐条通过。

### M4 · 收尾

**目标**：交付一个别人能装、能用、能贡献的东西。

**范围**：README 的 CLI 段落与实际输出对齐、GitHub Actions（Windows + Ubuntu）、构建产物、贡献指南。

## 版本管理

### 分支模型

```
main                    只接受来自 feature/* 的 PR，始终可运行
  │
  └─ feature/mN-<slug>     每个里程碑一个或多个功能分支
```

- 分支命名：`feature/m1-asset-registry`、`feature/m2-mcode-adapter`
- **不直接推 main**，所有变更走 PR
- PR 关闭对应的一个或多个任务，PR 描述里勾选任务清单

### 提交规范

Conventional Commits，scope 用里程碑号或模块名：

```
<type>(<scope>): <subject>

type: feat | fix | docs | test | refactor | chore | perf
scope: m0 | m1 | m2 | m3 | m4 | store | adapter-mcode | cli | security
```

示例：

```
feat(m1): [T1.07] 实现资产导入与目录规范化哈希
feat(m2): [T2.9] mcode Adapter 写入 MCP 段并保留原有格式
fix(m2): [T2.11] Claude Code 定点块编辑保留 .claude.json 其余字节
docs(007): 补充 v1 非目标清单
```

### 任务编号与提交的对应

**一个任务 = 一个提交**。下表中每个任务有唯一编号（如 `T1.07`），提交信息里带上编号。这样任何时候都能从 git log 反查进度：

```bash
git log --oneline | grep -o 'T[0-9]\+\.[0-9]\+' | sort -u
```

### 里程碑与版本号

| 里程碑 | 合并后打 tag | 说明 |
| --- | --- | --- |
| M0 | `m0-foundation` | 骨架可运行，实测完成 |
| M1 | `m1-registry` | 资产层可用 |
| M2 | `m2-deployment` | 部署闭环打通 |
| M3 | `m3-hardened` | 可信 |
| M4 | `v0.1.0` | 第一个可用版本 |

里程碑之间用小版本（`v0.1.0-alpha.1`）区分开发中的状态。

## 任务清单

**使用方式**：每完成一个任务就勾选，并在提交信息里带上任务编号。文件路径见 [003 Architecture](003-architecture.md)。

### 关键路径与并行

```
T0.1 → T0.2 → T0.5 → T0.6 ─┬─→ T1.1 ─→ T1.2 ─→ T1.6 ─→ T1.7 ─→ T1.10 ─┐
                           │        │                                 │
                           └─→ T0.9 (实测，可并行)                    │
                                                                          ▼
T2.1 → T2.2 → T2.7 → T2.8 → T2.12 → T2.13 → T2.14 → T3.x
        │       │        │        │
        └→ T2.3,T2.4,T2.5,T2.6 (可并行)  T2.9/T2.11 (依赖 T2.3/T2.4)
```

**M0 的实测（T0.9）必须与 M1 的代码工作并行推进**，因为它的结论可能反过来改 M1 的 Manifest 设计。

### M0 · 工程地基

| # | 任务 | 主要文件 | 验收 |
| --- | --- | --- | --- |
| [x] T0.1 | 项目骨架与依赖锁定 | `pyproject.toml`, `uv.lock` | `uv sync` 成功；`uv run capnest --version` 可执行 |
| [x] T0.2 | 包骨架 | `src/capnest/__init__.py`, `__main__.py`, `py.typed` | `python -m capnest --version` 可用 |
| [x] T0.3 | 异常体系与退出码映射 | `src/capnest/errors.py` | 8 种错误码全部有对应异常类与退出码 |
| [x] T0.4 | JSON 输出协议 | `src/capnest/jsonout.py` | 成功/失败 envelope 结构符合 [006 CLI](006-cli.md) 的协议 |
| [x] T0.5 | Typer 装配 + 全局选项 | `src/capnest/cli.py` | `--json` / `--workspace` / `--no-color` 全局生效；`--help` 分层清晰 |
| [x] T0.6 | 工作区定位 + `init` | `src/capnest/config.py`, `store/workspace.py`, `commands/init.py` | `capnest init ./ws` 生成完整骨架；重复 init 退出码 7 |
| [x] T0.7 | `doctor` 骨架 | `src/capnest/commands/doctor.py` | 检查 Python 版本与工作区；`--json` 结构符合 [006 CLI](006-cli.md) |
| [x] T0.8 | 代码风格与 CI 骨架 | `.editorconfig`, `pyproject.toml`（ruff）, `.github/workflows/ci.yml` | `ruff check` / `ruff format --check` 通过；CI 只跑 lint |
| [x] T0.9 | **实测 #1**：两个目标的 skills 落点与配置目录 | `scripts/phase0_probe.ps1`, `tests/fixtures/target_report.json`, `tests/fixtures/mcode_config.yaml`, `tests/fixtures/skill/SKILL.md` | 抓到的样本与 [005 Adapters](005-adapters.md) 的格式一致或记录差异 |
| [ ] T0.10 | **实测 #2**：配置合并语义（**推迟到第二刀**） | `docs/005-adapters.md`（补遗） | 明确回答「两个工具同时写同一配置时的合并规则」——依赖 MCP 写入场景 |
| [ ] T0.11 | **实测 #3**：mcode 用户级 MCP 落点（**推迟到第二刀**） | `docs/005-adapters.md`（结论） | 确认 MCP 写 `config.yaml` 的 `mcpServers` 段还是独立的 `mcp.json` |
| [x] T0.12 | 命名空间与格式词表定稿 | `docs/001`, `docs/002` | `io.capnest.capability/v1alpha1`；`mcp.local-config` / `mcp.registry-server-json` 拆分；`io.capnest.workflow/v1alpha1` |

**T0.12 是破坏性变更**，但 v1 未发布，此刻改零成本。**必须在 M1 写代码之前完成**，否则模型字段要返工。

**M0 出口条件**：`uv run capnest --json init ./ws` 与 `uv run capnest doctor --json` 均通过；T0.9 实测有书面结论；打 tag `m0-foundation`。

**T0.10 / T0.11 推迟到第二刀**：这两项实测的结论只影响 MCP 写入路径，而第一刀的资产类型只有 Skill、不写任何 Agent 共享配置文件。现在做它们只能得到一份「与 Skill 无关」的结论，因此推迟到 MCP 真正要落地时再做，编号保留。

### M1 · 资产层

| # | 任务 | 主要文件 | 验收 |
| --- | --- | --- | --- |
| [x] T1.1 | 全部数据模型 | `src/capnest/models.py` | [003 Architecture](003-architecture.md) 的模型全部实现；未知字段被忽略 |
| [x] T1.2 | 规范化内容哈希 | `src/capnest/hashing.py` | 符合规范化规则全部条目；跨平台固定样本测试通过 |
| [x] T1.3 | 文本归一与二进制判定 | `src/capnest/util/text.py` | CRLF/CR → LF；NUL 与不可解码判为二进制 |
| [x] T1.4 | 文件系统工具 | `src/capnest/util/fs.py` | 目录树复制保留权限；原子替换；Windows 目录联接可用 |
| [x] T1.5 | 隐藏 Unicode 扫描 | `src/capnest/security/scan.py` | 零宽 / bidi / tag / 同形异义四类均能检出；命中即阻断 |
| [x] T1.6 | 资产扫描与读取 | `src/capnest/store/assets.py` | `scan()` 遍历 `assets/`，校验 manifest，产出 `AssetRecord` |
| [x] T1.7 | 资产导入 | `src/capnest/store/assets.py` | `import_path()` 自动生成缺失的 `capability.yaml`；复制而非引用 |
| [x] T1.8 | 资产收编 | `src/capnest/store/assets.py` | `adopt_from_target()` 从 Agent 目录收编，保留原文件不动 |
| [x] T1.9 | Profile 与 Lock 仓库 | `src/capnest/store/profiles.py` | 读写 `profiles/*.yaml` 与 `*.lock.yaml` |
| [x] T1.10 | `add` 命令 | `src/capnest/commands/add.py` | 支持 `add <kind> <path>` 与 `add --from <target>:<name>`；Unicode 命中退出码 6 |
| [x] T1.11 | `list` 命令 | `src/capnest/commands/ls.py` | 表格输出 + `--json`；支持 `--type` 过滤 |
| [x] T1.12 | `search` 命令 | `src/capnest/commands/search.py` | 在 id / name / description / type 上子串匹配 |
| [x] T1.13 | `validate` 命令 | `src/capnest/commands/validate.py` | 10 项检查全部实现；error → 退出码 3 |
| [x] T1.14 | `profile` 命令组 | `src/capnest/commands/profile.py` | `create` / `list` / `show`；`show` 报告引用资产的缺失与版本 |
| [x] T1.15 | 演示资产 | `examples/data-agent/assets/skills/sql-analysis/` | Skill 一份（MCP / Workflow 样例随第二刀的 MCP 一起补） |
| [x] T1.16 | 单元测试 | `tests/test_models.py`, `test_hashing.py`, `test_scan.py`, `test_assets.py`, `test_profiles.py`, `test_validation.py`, `test_cli_m1.py` | 覆盖率 ≥ 80%（`deployment/` 除外） |
| [x] T1.17 | 文档对齐 | `README.md`, `SETUP.md`, `docs/006-cli.md` | CLI 段落与实际行为一致；`add --from` 写进文档 |
| [x] T1.18 | 资产来源标记 | `src/capnest/models.py`, `store/assets.py` | 收编来的资产在 `metadata.source` 里记下来源；`list` 显示 SOURCE 列 |
| [x] T1.19 | 批量收编 | `src/capnest/store/assets.py`, `commands/add.py` | `add --from <target>:*` 一次收编全部；容器目录与嵌套目录跳过并说明 |

**M1 出口条件**：M1 验收命令全部通过；打 tag `m1-registry`。

### M2 · 部署层

#### M2a · 只读部分（先做，无破坏性）

| # | 任务 | 主要文件 | 验收 |
| --- | --- | --- | --- |
| [x] T2.1 | 解析器 | `src/capnest/deployment/resolver.py` | Profile + 资产 → `DeploymentPlan`；缺失资产报错 |
| [x] T2.2 | Diff 引擎 | `src/capnest/deployment/diff.py` | 文件级与目录树级 unified diff |
| [x] T2.7 | Adapter 协议与能力矩阵 | `src/capnest/adapters/base.py` | `TargetCapabilities` / `TargetState` 定义 |
| [x] T2.8 | mcode 只读 | `src/capnest/adapters/mcode.py` | 读 `config.yaml` + `skills/`，归一化为 `TargetState`；不碰 `.builtin-skills/` |
| [x] T2.10 | Claude Code 只读 | `src/capnest/adapters/claude_code.py` | 读 `.claude.json` + `skills/`，归一化为 `TargetState` |
| [x] T2.12 | `plan` 命令 | `src/capnest/commands/plan.py` | 只读；不写任何文件；输出 create/update/unchanged |

**M2a 出口条件**：`plan` 能在真实机器上正确读出两个 Agent 的当前状态并与期望状态比对。

#### M2b · 写入部分

| # | 任务 | 主要文件 | 验收 |
| --- | --- | --- | --- |
| [x] T2.3 | 归属证明 | `src/capnest/deployment/ownership.py` | 未 claim 的路径拒绝写入；指纹不符视为漂移并拒绝 |
| [x] T2.4 | 原子写 + 预写事务 | `src/capnest/deployment/atomic.py` | stage/commit/abort/verify；提交失败自动回滚已提交部分 |
| [x] T2.5 | 备份与回滚 | `src/capnest/deployment/backup.py` | 备份已有文件；记录 `created_paths`；还原后逐字节一致 |
| [x] T2.6 | 部署状态 | `src/capnest/deployment/state.py` | `DeploymentRecord` 读写；per-target per-phase 状态 |
| [ ] T2.9 | mcode 写入 MCP 段（**推迟到第二刀**） | `src/capnest/adapters/mcode.py` | 定点块编辑 `mcpServers`；写前后 diff 校验，预期外变化即中止 |
| [ ] T2.11 | Claude Code 写入 MCP 段（**推迟到第二刀**） | `src/capnest/adapters/claude_code.py` | 定点块编辑 `mcpServers`；其余字节逐字保留；写前 mtime 检查 |
| [x] T2.13 | `apply` 命令 | `src/capnest/commands/apply.py` | 完整流程：扫描 → 归属 → 事务 → 确认 → 提交 → 记录 |
| [x] T2.14 | `status` 命令 | `src/capnest/commands/status.py` | 输出 up-to-date / drift / version-lag / never-deployed / failed |
| [x] T2.15 | `rollback` 命令 | `src/capnest/commands/rollback.py` | 还原 + 删除新建路径 + 移除记录 + 释放 claim |
| [x] T2.16 | `doctor` 完整版 | `src/capnest/commands/doctor.py` | Agent 路径、CLI 版本、能力矩阵、symlink 可用性 |
| [x] T2.18 | `inspect` 命令 | `src/capnest/commands/inspect.py` | 只读盘点目标侧已有的 skill；标出 managed / unmanaged / nested / container |
| [x] T2.17 | Golden fixture 与端到端测试 | `tests/test_adapters.py`, `tests/test_deployment.py`, `tests/test_cli_e2e.py` | 读样本 → 归一化 → 断言 `TargetState`；写回后除目标键外逐字节不变 |

**T2.18 capnest inspect**：目标侧盘点命令（只读），在 M2 合并后补上——它回答「目标里有哪些 skill、叫什么、CapNest 管不管」，是 `add --from` 的前置步骤。

**T2.9 / T2.11 推迟到第二刀**：这两项是 MCP Server 的写入路径，而第一刀的资产类型只有 Skill、不写任何 Agent 共享配置文件。编号保留，配套的实测 T0.10 / T0.11 同样在第二刀做。

**M2 出口条件**：M2 验收命令全部通过；两个 Agent 侧实际生效；打 tag `m2-deployment`。

### M3 · 闭环加固

| # | 任务 | 主要文件 | 验收 |
| --- | --- | --- | --- |
| [ ] T3.1 | 漂移检测 | `src/capnest/deployment/state.py`, `commands/status.py` | 外部改动 Agent 配置 → 报 drift；`--strict` 退出码 4 |
| [ ] T3.2 | 版本落后检测 | 同上 | 修改资产 → 报 version-lag；与漂移分开呈现 |
| [ ] T3.3 | 幂等性 | `src/capnest/commands/apply.py` | 重复 apply → UNCHANGED，不写盘不备份，退出码 0 |
| [ ] T3.4 | Apply→Rollback 往返测试 | `tests/test_backup.py` | 还原后与初始状态**逐字节一致** |
| [ ] T3.5 | 端到端 CLI 测试 | `tests/test_cli_e2e.py` | 临时工作区 + 临时 Agent HOME 跑完整六步闭环 |
| [ ] T3.6 | 验收标准脚本化 | `tests/test_acceptance.py` | [008 Acceptance](008-acceptance.md) 八条逐条有对应测试 |
| [ ] T3.7 | 失败路径测试 | `tests/test_failures.py` | 归属拒绝、Unicode 阻断、回滚冲突、缺资产 |
| [x] T3.8 | 多来源 manifest 与内容哈希 | `src/capnest/models.py`, `src/capnest/hashing.py` | `metadata.sources` 记录资产在哪些 Agent 侧出现过；`content_hash()` 忽略 manifest |
| [x] T3.9 | 收编即认领、去重与冲突识别 | `src/capnest/store/assets.py` | 收编后认领目标路径；同名同内容只并来源；同名不同内容记成冲突 |
| [x] T3.10 | `conflict` 命令组 | `src/capnest/commands/conflict.py`, `src/capnest/store/conflicts.py` | `list` 列出分歧；`resolve --use workspace\|<target>:<name>` 裁决并落盘 |
| [x] T3.11 | `dedupe` 命令 | `src/capnest/commands/dedupe.py` | 报告内容相同、名字不同的资产组 |
| [x] T3.12 | `sync` 编排命令 | `src/capnest/commands/sync.py`, `src/capnest/commands/apply.py` | 收编 → 去重 → 冲突 → 同步一条命令走完；同步后逐个校验两边一致 |
| [x] T3.13 | 多目标收编与通配符修正 | `src/capnest/commands/add.py`, `src/capnest/cli.py` | `add --from '*'` 收编所有目标；Windows 上不模拟 shell 通配符展开 |

**T3.8–T3.13 这一条线回答的是「真实怎么用」**：两个 Agent 侧已有的 skill 收成一份、
去重、看清分歧、裁过分歧、再同步回两边。它是 M1/M2 那些零件的**组合用法**，
不是新零件——所以它排在 M3 而不是 M1。

**M3 出口条件**：[008 Acceptance](008-acceptance.md) 八条全绿；打 tag `m3-hardened`。

### M4 · 收尾

| # | 任务 | 主要文件 | 验收 |
| --- | --- | --- | --- |
| [ ] T4.1 | 文档与实现对齐 | `README.md`, `SETUP.md`, `docs/006-cli.md` | 命令、参数、退出码、输出样例与实现完全一致 |
| [ ] T4.2 | CI 完整化 | `.github/workflows/ci.yml` | Windows + Ubuntu 双平台跑 lint + test；矩阵通过 |
| [ ] T4.3 | 构建产物 | `pyproject.toml`, `.github/workflows/release.yml` | `uv build` 产出 wheel + sdist |
| [ ] T4.4 | 贡献指南 | `CONTRIBUTING.md` | 说明分支模型、提交规范、任务编号对应 |
| [ ] T4.5 | 版本与发布 | `pyproject.toml`, tag | 打 tag `v0.1.0`；CHANGELOG 记录 M0–M4 |

**M4 出口条件**：全新机器上 `uv tool install` 后 `capnest doctor` 全绿。

## 工作量粗估与最大风险

仅供排期参考，误差可能 ±50%。

| 里程碑 | 任务数 | 人日 | 主要不确定性 |
| --- | --- | --- | --- |
| M0 | 12 | 1–1.5 | 含三项实测，可能超 |
| M1 | 17 | 2.5–3.5 | Manifest 校验规则的细致程度；收编既有资产的边界 |
| M2 | 17 | 4–6 | **最大不确定项**：两个 Agent 的配置格式是否真的无损可写 |
| M3 | 7 | 2–3 | 漂移检测要覆盖多少种「外部修改」形态 |
| M4 | 5 | 1–2 | 打包与 CI 的平台差异 |
| **合计** | **58** | **10.5–16** | |

**风险集中在 M2**。缓解措施是把它拆成两段：M2a 只做**只读**（读两个 Agent 的现有配置 → 归一化成内部结构 → 与期望状态比对），M2b 才做写入。只读部分如果出问题，不会有任何破坏性后果。

## 下一个

[008 Acceptance](008-acceptance.md) — 什么算做完了。
