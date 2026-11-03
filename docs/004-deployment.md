# 004 Deployment

本文定义 CapNest 在目标 Agent 上做了什么、遵守哪些规则、状态如何记录。它是 Agent 无关的：具体配置格式属于 [005 Adapters](005-adapters.md)。

## 安全规则

这七条是不可协商的前提。任何实现若违反其中一条，都是缺陷而不是取舍。

| # | 规则 |
| --- | --- |
| 1 | Manifest 与 Lockfile 不保存明文密钥、密码 |
| 2 | 敏感信息用 `${ENV_VAR}` 引用 |
| 3 | **无法证明归属的文件一律不碰** |
| 4 | 每次部署先出 Diff |
| 5 | 改动前自动备份 |
| 6 | 隐藏 Unicode（零宽 / bidi / tag / 同形异义）扫描为阻断项 |
| 7 | Agent 只读 + 申请，不默认获得资产修改权限 |

### 实现映射

| 规则 | 实现方式 |
| --- | --- |
| 1 | Manifest Schema 校验时拒绝含疑似密钥的字段值 |
| 2 | 资产配置中使用 `${ENV_VAR}` 引用，部署时解析；未定义时报错中止，不写空值 |
| 3 | `state/ownership.json` 记录已 claim 的路径与指纹；未 claim 的路径拒绝写入 |
| 4 | `plan` 输出 diff；`plan` 与 `apply` 接受相同的 `--profile` / `--target` 并共用同一计算函数 |
| 5 | 每次 `apply` 前快照至 `state/backups/<timestamp>/` |
| 6 | `add` 与 `apply` 前跑扫描，命中即阻断并返回退出码 6 |
| 7 | CapNest MCP Server 只暴露只读 + 申请类工具（远期） |

## v1 的部署边界

| 维度 | v1 | 说明 |
| --- | --- | --- |
| 资产类型 | Skill、MCP Server 可部署；Workflow **只登记** | 没有执行引擎，部署了也没地方用 |
| 目标 | `codex`、`claude-code` | `openclaw` 规划中 |
| 形态 | `copy`（默认）、`symlink`（opt-in） | Windows 上 `copy` 是唯一普遍可用的方式；`symlink` 需开发者模式 |
| 变更类型 | 只做「新增 / 更新」，**不做删除** | 见下 |

### 只做新增与更新

v1 的 apply 语义是「确保目标上存在且一致」，不是「让目标与 Profile 完全相同」。Profile 中移除某个能力后，v1 不会去 Agent 侧删它。

`plan` 的输出会显式标注 `[skipped: removal not supported in v1]`，**避免静默不一致**。

### 不做的事

| 不做 | 何时做 |
| --- | --- |
| 能力卸载 / 回收 | v0.2 |
| `pull` 模式部署（Agent 主动拉取） | v0.2 |
| plugin 包部署（写 marketplace 缓存目录） | v0.2，优先走「生成 plugin 包 → 调用 Agent 的安装命令」 |
| 依赖版本范围求解的通用实现 | 需要时 |
| 多 Agent 并发写同一目标 | 出现真实需求时（v1 声明为不支持） |

## 通用部署算法

```
对每个 target：
  1. current = adapter.read()                    # 读现状并归一化
  2. desired = 由 DeploymentPlan 推导的期望状态
  3. intents = adapter.plan(desired, current)    # 只产出「新增/更新」
  4. 对每个 intent：
       a. ownership 检查 —— 目标已存在且未 claim → 报错终止
       b. 生成 diff（文件级 / 目录树级）
  5. 展示或提交
```

`plan` 只做第 1–4 步然后停下，**不写任何文件**。`apply` 走完整流程。

## 归属证明（ownership）

| 场景 | 行为 |
| --- | --- |
| 目标路径不存在 | 直接创建，claim 该路径 |
| 目标路径存在且已被 claim，指纹一致 | 允许更新（先备份） |
| 目标路径存在且已被 claim，指纹**不一致** | 视为漂移，**拒绝写入**，退出码 7 |
| 目标路径存在但未被 claim | **拒绝写入**，退出码 7，提示用 `--force` 或先 `add --from` 收编 |
| MCP 配置文件的共享部分 | 只在 `mcp_servers.<name>` / `mcpServers.<name>` 内 upsert，其余字节逐字保留 |

**指纹定义**：被管理内容的规范化哈希。文件级用文件内容哈希，目录级用目录哈希。

**Claim 是累积的**：一次成功的 apply 之后，被修改或新建的路径都会记入 `state/ownership.json`，指纹为写入后的期望值。

## 原子写与预写事务

```python
@dataclass
class WriteIntent:
    path: Path
    content: bytes | None             # None 表示删除
    mode: DeploymentMode

@dataclass
class Transaction:
    intents: list[WriteIntent]
    backups: dict[str, str]           # 原路径 → 备份路径
    fingerprints: dict[str, str]      # 写入后的期望指纹


class AtomicWriter:
    def stage(self, intents: list[WriteIntent]) -> Transaction: ...
    def commit(self, tx: Transaction) -> None: ...
    def abort(self, tx: Transaction) -> None: ...
    def verify(self, tx: Transaction) -> list[str]: ...   # 返回校验失败的路径
```

**语义**：`stage` 只写临时文件并计算指纹；`commit` 逐个做「备份原文件 → 原子替换 → 校验指纹」，任一失败则回滚已提交的部分。

**写后校验校验的是「只改了想改的」，不是「写成功了」。** 对共享配置文件尤其重要：序列化后的内容与原文做 diff，只允许目标键相关的行变化，出现任何预期外变化即中止并报错。

## 备份与回滚

### 备份

`apply` 提交前，对**每一个将被修改或新建的路径**：

| 路径状态 | 备份动作 |
| --- | --- |
| 已存在（将被修改） | 复制到 `state/backups/<ts>/<target>/<相对路径>` |
| 不存在（将新建） | 在 `created_paths` 中记录，**不备份** |

新建的目录（如 `~/.codex/skills/sql-analysis/`）在 `created_paths` 里记绝对路径。

### 回滚

```
1. 定位部署记录（默认该 target 最近一条成功记录）
2. 对每个 backup_ref 下的文件：
     还原到原路径（原子替换）
3. 对 created_paths 中的路径：
     删除（先确认内容与部署时写入的一致；不一致则拒绝并提示）
4. 从 state/deployments.json 移除该记录
5. 释放对应的 ownership claim
```

**回滚不还原用户后续的手工修改**：若某路径当前内容既不等于备份、也不等于 CapNest 写入的状态，说明用户动过，v1 拒绝覆盖并提示人工介入。

## 部署状态模型

每次部署产生一条记录，存于 `state/deployments.json`：

| 字段 | 说明 |
| --- | --- |
| `id` | 部署 ID |
| `profile` | 关联的 Profile 名 |
| `target` | 目标 Agent |
| `created_at` | 时间戳 |
| `mode` | 部署形态 |
| `phase_status` | 各阶段状态，至少含 `assets`（Skill 目录）与 `mcp`（MCP 配置段） |
| `applied_state_hash` | **apply 完成后目标 Agent 配置的哈希**，用于检测外部修改 |
| `asset_hashes` | 部署时各资产的哈希，用于检测资产更新 |
| `diff_hash` | 本次 Diff 的哈希，仅用于审计 |
| `backup_ref` | 对应备份目录 |
| `created_paths` | 本次新建的路径，回滚时删除 |
| `error` | 失败原因 |

**状态粒度是 per-target per-phase**：`NotRun` / `Applied` / `Unchanged` / `Skipped` / `Failed`。每个 target 一条记录，失败单独标 `FAILED`——**聚合状态不得掩盖逐目标失败**。

### 两种检测，含义不同

两者回答的是不同问题，实现上必须分开：

| 检测 | 问题 | 比对方式 |
| --- | --- | --- |
| **漂移**（drift） | Agent 侧配置被外部改动了？ | 重新计算当前目标状态哈希，与 `applied_state_hash` 比对，不一致即报 drift |
| **版本落后**（version lag） | CapNest 里的资产更新了？ | 将 `asset_hashes` 与当前 `assets/` 中对应资产的哈希逐一比对 |

`applied_state_hash` 是**应用之后的目标状态哈希**，不是 Diff 的哈希——两者不可互换，否则每次检查都会误报漂移。`diff_hash` 仅作审计留痕，不参与任何判定。

### 两个哈希的规范化基准必须一致

- `applied_state_hash`：哈希**归一化后的 TargetState**（skills 目录内容哈希 + 归一化后的 MCP 定义），不是目标配置文件的原始字节。
- `asset_hashes`：哈希**资产目录**，按 [003 Architecture](003-architecture.md) 的规范化规则。

## 幂等性

同一 Profile 重复 `apply`：

- 目标已是期望状态 → 该项 `phase_status = UNCHANGED`，不写盘、不备份
- 整体命令仍返回 0

**幂等判定的依据是内容哈希，不是 mtime。**

## 已知风险与降级策略

| 风险 | 影响 | 降级 |
| --- | --- | --- |
| 目标配置与 Agent CLI 并发写 | CapNest 的改动被覆盖 | 写前 mtime 检查 + 定点块编辑缩小损失面；`status` 能检出漂移 |
| TOML 序列化产生非预期 diff | 用户配置被「整理」了 | 写入前后 diff 校验，预期外变化直接中止 |
| 目标上有同名非 CapNest 资产 | 覆盖用户数据 | 归属证明拒绝；引导 `add --from` 收编 |
| Windows 无开发者模式 | `symlink` 不可用 | 默认 `copy`；`doctor` 明确提示 |
| Agent CLI 版本变化导致配置格式变化 | 写入格式失效 | golden fixture 测试；`doctor` 报告版本；写入前做结构探测 |
| 目标 skills 目录出现嵌套结构 | 目录级 diff 假设失效 | v1 只支持单层，检测到嵌套报 warn 并拒绝覆盖 |

## 下一个

[005 Adapters](005-adapters.md) — 每个目标 Agent 的配置长什么样，以及怎么读写。