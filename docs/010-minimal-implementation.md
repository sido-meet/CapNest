# 010 Minimum engineering implementation

蓝图说清「要做成什么样」，本文说清「**第一个能跑的东西长什么样**」。

本文是实现的第一优先级文档。`007-tasks` 的 58 项是完整 v1 的工作量分解；本文定义的是其中**第一刀**：一条端到端可验证的最小链路，用最少的代码解决一个具体问题。

## 1. 定义

**最小工程实现 = 能被独立验证的最小完整闭环。**

不是「功能最少的版本」，是「代码最少、但链路完整」的版本。三条判据：

| 判据 | 含义 |
| --- | --- |
| 端到端可断言 | 不是 demo，是有退出码、有状态记录、能回滚的真实链路 |
| 每层可独立验证 | 读能独立测、写能独立测，两者先在只读阶段汇合 |
| 砍掉的都不阻塞闭环 | 砍功能可以，砍链路的一环不行 |

功能多而链路断的叫 Alpha。功能少但链路完整、可断言、可回滚的，才是最小工程实现。

## 2. 唯一要解决的问题

第一刀只解决这一个问题：

> **我把一份 Skill 装进 mcode 和 Claude Code，两边内容一致。改这一份，两边都能同步；同步前能看到差异；出了问题能一键还原。**

「一份能力，两处同步」是 CapNest 存在的理由，所以**目标不能收窄到只有一个 Agent**。

**为什么是 mcode 与 Claude Code，而不是 Codex**：CapNest 本身就在 Codex 里开发，把被测对象部署进 `~/.codex` 等于让它改写开发宿主自己——技能目录会被热加载、配置会被并发读写，测试结果不可信；而且跨 Agent 一致性的价值恰恰体现在两个**不同的** Agent 上，其中一个是自己就退化成了自测。Codex 的 Adapter 推到 v0.2。

而收窄**资产类型**不影响问题成立——Skill 已经足以暴露核心难点（归属证明、原子写、diff、回滚、跨目标一致性）。

## 3. 最小边界

| 维度 | 第一刀取值 | 砍掉了什么 | 为什么现在砍不伤闭环 |
| --- | --- | --- | --- |
| 资产类型 | **只有 Skill** | MCP Server、Workflow | MCP 要改写 Agent 的共享配置文件，风险高一档；Workflow 不部署 |
| 部署目标 | `mcode` + `claude-code` | 其他 Agent | 跨 Agent 一致性就是问题本身，不能砍 |
| 部署形态 | **只有 `copy`** | `symlink` | `symlink` 在 Windows 上需要开发者模式，不是普遍能力；目录复制是唯一普遍可用的形态 |
| 命令 | 7 个 | `list` `search` `validate` `doctor` 完整版 | 这几个是「看」的工具，不在闭环链路上，可后补 |
| 存储 | `assets/` + `profiles/` + `state/*.json` | 数据库 | 几十个资产的量级，扫目录足够 |
| 安全底线 | 归属证明、备份、隐藏 Unicode 阻断 | 权限类别词表、密钥库 | 三条底线覆盖「不毁用户数据」 |

### 闭环的七条命令

```
init → add → profile create → plan → apply → status → rollback
```

`list` / `search` / `validate` / `doctor` 属于便利与自检工具，在第二刀补齐（见 §8 路线）。

### 明确不做（第一刀）

| 不做 | 原因 |
| --- | --- |
| MCP Server 部署 | 要写共享配置文件，风险与工作量高一档 |
| Workflow | 只登记不部署，没有执行引擎 |
| 漂移检测 | 需要 `applied_state_hash` 的完整语义，与第二刀的状态记录一起做 |
| 版本落后检测 | 同上 |
| Lockfile / 依赖求解 | 只有一个资产类型时，版本一致性靠内容哈希就够 |
| 能力卸载 / 删除 | v1 全部语义都是「只新增与更新」 |
| `symlink` | 需要开发者模式 |
| 隐藏 Unicode 扫描以外的检查 | 只留四类字符判定 |
| `--json` 的 GUI 用途 | 协议先定好，消费者后到 |

## 4. 最小数据模型

只保留闭环必需的字段。完整模型见 [003 Architecture](003-architecture.md)，本节是第一刀真正要写的。

### 资产 Manifest

```yaml
apiVersion: io.capnest.capability/v1alpha1
kind: Capability
metadata:
  id: skills/sql-analysis        # 必填，<目录名>/<name>
  name: SQL Analysis             # 必填
  version: 1.0.0                 # 必填
spec:
  type: skill                     # 必填
  format: agentskills.io          # 必填
  entrypoint: ./SKILL.md          # 必填，相对资产目录
```

第一刀的**资产级** Manifest 不实现 `dependencies`、`permissions`、`deployment`。Profile 保留 `components` 与 `targets`（否则闭环无内容可部署），只是不带 `components[].version` 版本约束：

```yaml
apiVersion: io.capnest.capability/v1alpha1
kind: CapabilityProfile
metadata:
  id: data-agent
  name: Data Agent
  version: 1.0.0
spec:
  components:
    - ref: skills/sql-analysis
  targets:
    - mcode
    - claude-code
```

### 状态文件

`state/ownership.json`：

```json
{
  "C:/Users/x/.minimax/skills/sql-analysis": "sha256:9f2c…"
}
```

`state/deployments.json`：

```json
[
  {
    "id": "20261103T142500Z-mcode",
    "profile": "data-agent",
    "target": "mcode",
    "created_at": "2026-11-03T14:25:00Z",
    "mode": "copy",
    "applied_paths": ["C:/Users/x/.minimax/skills/sql-analysis"],
    "backups": {},
    "created_paths": ["C:/Users/x/.minimax/skills/sql-analysis"],
    "asset_hashes": {"skills/sql-analysis": "sha256:9f2c…"}
  }
]
```

第一刀**没有** `phase_status`（只有一个资产类型一个阶段）、**没有** `diff_hash`、**没有** `applied_state_hash`（漂移检测才需要）。这些在第二刀补。

## 5. 最小文件集

以下是第一刀**必须创建**的文件。每个文件后面的签名是它的全部职责——超出这个范围的一律推到第二刀。

```
pyproject.toml                    # uv + hatchling，依赖与入口点
src/capnest/__init__.py           # __version__
src/capnest/__main__.py           # python -m capnest
src/capnest/cli.py                # Typer app，全局 --json/--workspace/--no-color
src/capnest/context.py            # AppContext：工作区路径 + 输出通道
src/capnest/errors.py             # 异常 → 退出码 + 结构化 error
src/capnest/jsonout.py            # ok/command/data/error envelope
src/capnest/models.py             # 第一刀所需的 4 个 Pydantic 模型
src/capnest/hashing.py            # 目录规范化哈希
src/capnest/config.py             # config.yaml 读写
src/capnest/security/scan.py      # 隐藏 Unicode 扫描
src/capnest/util/fs.py            # 目录复制 / 原子替换
src/capnest/util/text.py          # 换行归一 / 二进制判定
src/capnest/store/workspace.py    # 工作区路径解析
src/capnest/store/assets.py       # 扫描 / 导入
src/capnest/store/profiles.py     # Profile 读写
src/capnest/commands/init.py
src/capnest/commands/add.py
src/capnest/commands/profile.py
src/capnest/commands/plan.py
src/capnest/commands/apply.py
src/capnest/commands/status.py
src/capnest/commands/rollback.py
src/capnest/deployment/resolver.py   # Profile + 资产 → 期望状态
src/capnest/deployment/diff.py       # 目录树 unified diff
src/capnest/deployment/atomic.py     # 暂存 → 提交 → 指纹校验
src/capnest/deployment/ownership.py  # 归属证明
src/capnest/deployment/backup.py     # 备份 / 还原
src/capnest/deployment/state.py      # 部署记录读写
src/capnest/adapters/base.py         # Adapter 协议 + TargetState
src/capnest/adapters/mcode.py        # skills 目录读写
src/capnest/adapters/claude_code.py  # skills 目录读写
tests/…
```

**约 30 个源文件**。这是「一个能跑的 CapNest」的物理下限，再减就要破坏分层。

### 关键接口

```python
# hashing.py
def hash_dir(path: Path, *, exclude: Sequence[str] = DEFAULT_EXCLUDES) -> str: ...
def hash_file(path: Path) -> str: ...

# store/assets.py
@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    kind: CapabilityType
    path: Path
    manifest: Capability
    hash: str

class AssetStore:
    def scan(self) -> list[AssetRecord]: ...
    def import_path(self, src: Path) -> AssetRecord: ...

# adapters/base.py
@dataclass(frozen=True)
class TargetState:
    skills: dict[str, str]            # skill 名 → 内容哈希

class Adapter(Protocol):
    target: str
    def capabilities(self) -> TargetCapabilities: ...
    def read(self) -> TargetState: ...
    def plan(self, desired: DesiredState) -> list[WriteIntent]: ...
    def verify(self, expected: TargetState) -> VerificationResult: ...

# deployment/atomic.py
class AtomicWriter:
    def stage(self, intents: list[WriteIntent]) -> Transaction: ...
    def commit(self, tx: Transaction) -> None: ...
    def abort(self, tx: Transaction) -> None: ...
    def verify(self, tx: Transaction) -> list[str]: ...

# deployment/ownership.py
class OwnershipRegistry:
    def claim(self, path: Path, fingerprint: str) -> None: ...
    def owned_by_us(self, path: Path) -> bool: ...
    def release(self, path: Path) -> None: ...
```

第一刀的 `TargetState` 只有 `skills` 一个字段，MCP 段在第二刀加入。

## 6. 实施顺序

十步，**严格串行**，每步都有可执行的验收命令。每步一个提交。

| 步 | 做什么 | 涉及文件 | 验收 |
| --- | --- | --- | --- |
| 1 | 骨架与输出通道 | `pyproject.toml`, `__init__`, `__main__`, `cli.py`, `errors.py`, `jsonout.py` | `uv run capnest --version`；`uv run capnest --json badcmd` 退出码 2 且输出合法 JSON |
| 2 | 工作区与 `init` | `config.py`, `context.py`, `store/workspace.py`, `commands/init.py` | `capnest init ./ws` 生成骨架；重复 init 退出码 7 |
| 3 | 数据模型与哈希 | `models.py`, `hashing.py`, `util/text.py` | 哈希规则表逐条有单测；同一目录两次哈希相同，改动一个字节即变 |
| 4 | `add` 与扫描 | `store/assets.py`, `commands/add.py`, `security/scan.py`, `util/fs.py` | `capnest add skill ./x` 复制进 `assets/skills/x/` 并生成 `capability.yaml`；Unicode 命中退出码 6 |
| 5 | `profile create` | `store/profiles.py`, `commands/profile.py` | 生成 `profiles/data-agent.yaml`；同名拒绝退出码 7 |
| 6 | Adapter 只读 | `adapters/base.py`, `adapters/mcode.py`, `adapters/claude_code.py`, `deployment/resolver.py` | 能读出两个 Agent 的 `skills/` 现状并归一化成 `TargetState` |
| 7 | `plan` | `deployment/diff.py`, `commands/plan.py` | 输出目录树 diff；**运行后目标目录无任何变化**（用 mtime 断言） |
| 8 | 归属、备份、原子写、`apply` | `deployment/ownership.py`, `atomic.py`, `backup.py`, `state.py`, `commands/apply.py` | apply 后两个 Agent 都有该 skill 且内容哈希一致；未 claim 的同名目录拒绝写入（退出码 7） |
| 9 | `status` | `commands/status.py` | 列出每个目标的部署记录与当前状态 |
| 10 | `rollback` | `commands/rollback.py` | 回滚后目标目录**逐字节**回到初始状态（无该目录即该目录消失） |

### 为什么是这个顺序

- **只读先于写入**（第 6 步在第 8 步之前）：读错了不会毁用户数据，这是整个项目风险最高的部分。
- **plan 先于 apply**（第 7 步在第 8 步之前）：先能看见差异，才允许落盘。
- **state 晚于写**（第 8 步才引入）：状态记录服务于回滚，没有写就没有状态。
- **rollback 最后**（第 10 步）：它依赖前面的记录格式，是最后一个能发现设计漏洞的地方。

### 提交规范

```
feat(m0): [T0.1] 项目骨架与依赖锁定
feat(m0): [T0.5] Typer 装配与全局选项
feat(m1): [T1.2] 目录规范化内容哈希
feat(m2): [T2.8] mcode Adapter 只读实现
feat(m2): [T2.13] apply 命令完整流程
feat(m2): [T2.15] rollback 命令实现
```

任务编号沿用 `007-tasks` 的号段。

## 7. 第一刀的验收

一条命令序列 + 六条断言，全部可脚本化：

```powershell
uv run capnest init .\ws
uv run capnest --workspace .\ws add skill examples\data-agent\assets\skills\sql-analysis
uv run capnest --workspace .\ws profile create data-agent --asset skills/sql-analysis --target mcode --target claude-code
uv run capnest --workspace .\ws plan   --profile data-agent --target mcode,claude-code
uv run capnest --workspace .\ws apply  --profile data-agent --target mcode,claude-code --yes
uv run capnest --workspace .\ws status
uv run capnest --workspace .\ws rollback --target mcode
```

全局选项 `--workspace` 放在子命令之前；工作区解析规则见 [006 CLI](006-cli.md) 的「工作区解析」。

| # | 断言 |
| --- | --- |
| 1 | `plan` 之后两个 Agent 的 skills 目录与执行前逐字节一致 |
| 2 | `apply` 之后两个 Agent 都有该 skill，内容哈希与 `assets/` 中一致 |
| 3 | 目标上已存在同名、且不由 CapNest 管理的目录 → `apply` 退出码 7，不覆盖 |
| 4 | 重复 `apply` → 退出码 0，文件 mtime 不变（幂等） |
| 5 | `rollback` 之后目标目录回到初始状态（逐字节） |
| 6 | 任一步失败都不留下半成品（要么没写，要么写完整） |

第 6 条是**事务性**的验收，也是最难的一条：`apply` 要么全成功，要么把已写的部分恢复到原样。

## 8. 路线

| 刀 | 内容 | 风险 |
| --- | --- | --- |
| **第一刀**（本文） | Skill → 两个 Agent，copy，七条命令闭环 | 低：只碰目录复制 |
| 第二刀 | MCP Server 部署（写 `config.yaml` / `.claude.json`）+ `list` `search` `validate` `doctor` | **高**：共享配置文件的无损改写 |
| 第三刀 | 漂移检测、版本落后、Lockfile、依赖求解 | 中 |
| 第四刀 | GUI、MCP Discovery、更多目标、plugin 形态 | 低 |

**先切低风险的，是为了让第二刀失败时不至于推倒重来。** 如果先做 MCP，共享配置文件的写入问题会暴露在还没有闭环骨架的时候，返工成本高得多。

## 9. 三条止损线

第一刀如果卡住，按这三条处理：

| 卡在哪 | 止损动作 |
| --- | --- |
| 归属证明与回滚互相打架 | 先把回滚降级为「只删除本次新建的路径」，不做文件还原；归属证明保留 |
| 目录 diff 太慢或太吵 | 降级为「按文件哈希逐个列出差异」，不生成 unified diff 文本 |
| 两个 Agent 的 skills 目录结构不一致 | 只支持单层目录，检测到嵌套就报 warn 并拒绝覆盖（[005 Adapters](005-adapters.md) 已有结论） |

三条都不动链路，只动实现细节。

## 10. 与其他文档的关系

| 文档 | 作用 |
| --- | --- |
| [007 Tasks](007-tasks.md) | 完整 v1 的 58 项任务与里程碑，本文的十步是其中的一段 |
| [003 Architecture](003-architecture.md) | 完整工程结构与数据模型，本文是它的第一刀子集 |
| [004 Deployment](004-deployment.md) | 部署语义与安全规则，本文实现其中的 Skill 子集 |
| [005 Adapters](005-adapters.md) | 两个 Agent 的配置格式，本文只用其 skills 部分 |
| [008 Acceptance](008-acceptance.md) | v1 的八条验收，本文是第一刀的六条子集 |
