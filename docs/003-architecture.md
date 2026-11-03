# 003 Architecture

## 技术选型

| 模块 | 技术 | 职责 |
| --- | --- | --- |
| Core | Python 3.11 | 核心业务逻辑 |
| CLI | Typer | 命令入口 |
| Schema | Pydantic | Manifest 校验与数据模型 |
| Storage | File System | 资产与状态 |
| Version | Git + SHA256 | 版本与完整性 |
| Adapter | Python | Agent 配置转换 |
| MCP | MCP Python SDK | Agent 能力发现接口（远期） |
| GUI | Tauri v2 + Svelte 5 | 后续可视化 |

选型理由：

- **Python 3.11**：与 MCP Python SDK、Agent Skills 生态一致，跨平台可用。
- **Typer**：类型注解即 CLI 定义，减少样板。
- **Pydantic**：Manifest 的单一校验来源，同时可生成 JSON Schema。
- **File System**：文件是事实来源，状态用 JSON 文件，索引直接扫目录，避免双写不一致。
- **Git + SHA256**：Git 提供版本历史与协作，SHA256 提供内容级不可变性验证。
- **Tauri v2 + Svelte 5**：GUI 体积小、启动快，后端复用 Python Core（通过 `capnest --json`）。

### 依赖冻结（v1）

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| `typer` | ≥0.12 | CLI 框架 |
| `rich` | ≥13 | 终端表格与彩色 diff |
| `pydantic` | ≥2.7 | 数据模型与校验 |
| `pyyaml` | ≥6.0 | Manifest / Profile / Lockfile |
| `tomlkit` | ≥0.13 | TOML **无损**读写（v0.2 的 Codex Adapter 才需要，v1 不引入） |

**标准库够用、不引入**：`hashlib`、`difflib`、`shutil`、`tomllib`（只读探测）、`json`、`unicodedata`、`sqlite3`（v1 不用）。

**开发依赖**：`pytest`、`pytest-cov`、`ruff`。

v1 不引入 TOML 依赖：两个目标的配置分别是 YAML 与 JSON，用 `pyyaml` 与标准库 `json` 即可。Codex Adapter 落在 v0.2，届时再引入 `tomlkit`——Codex 的 `config.toml` 里有大量注释与手写格式，`tomllib` 只读、普通 `toml` 会重排格式，只有 tomlkit 能 round-trip。

**也不引入 `platformdirs`**：两个目标的 home 位置是已知的（`~/.minimax` 与 `~/.claude`），且可用 `CAPNEST_TARGET_HOME_<TARGET>` 覆盖，`Path.home()` 就够用。

## 分层

```
┌──────────────────────────────────────┐
│  CLI  /  Desktop UI  /  Agent MCP    │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│            CapNest Core              │
│  Registry · Manifest · Resolver      │
│  Validator · Deployment              │
│  Version Manager                     │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│            Adapter Layer             │
│  mcode · Claude Code                 │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│         Canonical Asset Store        │
│  MCP · Skills · Workflows · Profiles │
└──────────────────────────────────────┘
```

所有业务规则都在 Core，**CLI、GUI、Agent MCP 三个入口共享同一套实现**，不允许各自复制逻辑。

| 组件 | 职责 |
| --- | --- |
| Registry | 资产的登记、索引、检索、元数据 |
| Manifest | 读写与校验 Manifest / Lockfile |
| Resolver | 依赖解析、版本约束求解、目标选择 |
| Validator | Manifest、依赖、路径、权限校验 |
| Deployment | Diff 计算、Apply、Backup、Rollback、漂移与版本落后检测 |
| Version Manager | 内容哈希、版本比较、锁定 |

### Adapter Layer

每个 Adapter 只负责两件事：**读**——把目标 Agent 的现有配置解析成内部结构；**写**——把内部结构转换成目标格式并写入。

Adapter 不做版本决策、不做依赖解析，这些属于 Core。Adapter 的具体规格见 [005 Adapters](005-adapters.md)。

## 依赖方向

依赖只能从上往下，**下层不知道上层的存在**：

```
cli.py  →  commands/  →  deployment/  →  adapters/  →  store/  →  util/
                        ↘ security/          ↘ models.py / hashing.py / config.py
```

- `commands/` 只做参数解析与输出编排，业务逻辑一律下沉
- `deployment/` 是**与 Agent 无关**的核心：解析、diff、原子写、备份、状态
- `adapters/` 是唯一知道 mcode / Claude Code 长什么样的地方
- `store/` 只碰文件系统，不碰 Agent 目录

## 仓库文件树

```
CapNest/
├── pyproject.toml               # uv / hatchling，依赖与入口点
├── README.md
├── SETUP.md
├── LICENSE
├── .gitattributes
├── .gitignore
├── .editorconfig
├── .python-version
├── .github/workflows/ci.yml
│
├── docs/
│   ├── 000-philosophy.md … 010-minimal-implementation.md
│   └── README.md
│
├── src/
│   └── capnest/
│       ├── __init__.py          # __version__
│       ├── __main__.py          # python -m capnest
│       ├── cli.py               # Typer app 装配、全局 --json、命令注册
│       ├── context.py           # AppContext：工作区 / 配置 / 输出通道
│       ├── errors.py            # 异常体系 → 退出码 + 结构化错误
│       ├── jsonout.py           # --json 输出协议
│       ├── models.py            # 全部 Pydantic 模型
│       ├── hashing.py           # 规范化内容哈希
│       ├── config.py            # config.yaml 读写
│       │
│       ├── commands/            # 每个命令一个模块
│       │   ├── __init__.py
│       │   ├── init.py
│       │   ├── add.py
│       │   ├── ls.py
│       │   ├── search.py
│       │   ├── validate.py
│       │   ├── profile.py
│       │   ├── plan.py
│       │   ├── apply.py
│       │   ├── status.py
│       │   ├── rollback.py
│       │   └── doctor.py
│       │
│       ├── store/               # 事实来源：文件系统
│       │   ├── __init__.py
│       │   ├── workspace.py      # 工作区路径解析
│       │   ├── assets.py         # 资产仓库：扫描 / 导入 / 收编
│       │   └── profiles.py       # Profile 与 Lockfile 仓库
│       │
│       ├── deployment/           # 部署引擎（与 Agent 无关的核心）
│       │   ├── __init__.py
│       │   ├── resolver.py       # Profile → DeploymentPlan
│       │   ├── diff.py           # unified diff 计算
│       │   ├── atomic.py         # 原子写 + 预写事务 + 指纹校验
│       │   ├── ownership.py      # 归属证明
│       │   ├── backup.py         # 备份 / 回滚
│       │   └── state.py          # 部署状态读写
│       │
│       ├── adapters/             # Agent 适配层
│       │   ├── __init__.py       # Adapter 注册表
│       │   ├── base.py           # Adapter 协议 + 能力矩阵
│       │   ├── mcode.py
│       │   └── claude_code.py
│       │
│       ├── security/
│       │   ├── __init__.py
│       │   └── scan.py           # 隐藏 Unicode 扫描
│       │
│       └── util/
│           ├── __init__.py
│           ├── fs.py             # 目录树复制 / 原子替换 / 联接
│           └── text.py           # 换行归一化 / 编码探测
│
├── tests/
│   ├── conftest.py               # 临时工作区、临时 Agent HOME
│   ├── fixtures/
│   │   ├── mcode_config.yaml     # mcode 配置样本（M0 实测抓取）
│   │   ├── claude.json           # Claude Code 配置样本（M0 实测抓取）
│   │   ├── skill/                # 样本 Skill（SKILL.md + capability.yaml）
│   │   └── mcp/                  # 样本 MCP Server
│   ├── test_hashing.py
│   ├── test_models.py
│   ├── test_assets.py
│   ├── test_profiles.py
│   ├── test_resolver.py
│   ├── test_diff.py
│   ├── test_atomic.py
│   ├── test_backup.py
│   ├── test_scan.py
│   ├── test_mcode_adapter.py
│   ├── test_claude_adapter.py
│   └── test_cli_e2e.py
│
├── examples/
│   └── data-agent/               # 008 Acceptance 的首个演示项目
│       ├── assets/
│       │   ├── skills/sql-analysis/{capability.yaml, SKILL.md}
│       │   ├── mcp/database/{capability.yaml, server.json}
│       │   └── workflows/data-diagnosis/{capability.yaml, workflow.yaml}
│       └── profiles/data-agent.yaml
│
└── scripts/
    └── phase0_probe.ps1          # M0 三项实测的脚本
```

## 数据模型

全部使用 Pydantic v2，统一 camelCase 别名，**允许未知字段**（forward compatible）。

```python
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Base(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",          # 未知字段一律忽略
        frozen=True,            # 领域对象不可变
    )


API_VERSION = "io.capnest.capability/v1alpha1"


class CapabilityType(StrEnum):
    SKILL = "skill"
    MCP_SERVER = "mcp-server"
    WORKFLOW = "workflow"


class DeploymentMode(StrEnum):
    COPY = "copy"
    SYMLINK = "symlink"


class PhaseStatus(StrEnum):
    NOT_RUN = "not_run"
    APPLIED = "applied"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    FAILED = "failed"


class Dependency(Base):
    ref: str                                   # 资产 ID 全名
    version: str | None = None
    optional: bool = False


class Permissions(Base):
    requested: list[str] = []


class DeploymentOptions(Base):
    mode: DeploymentMode = DeploymentMode.COPY
    enabled: bool = True


class CapabilitySpec(Base):
    type: CapabilityType
    format: str
    entrypoint: str                            # 相对资产目录
    dependencies: list[Dependency] = []
    permissions: Permissions = Permissions()
    deployment: DeploymentOptions | None = None


class CapabilityMetadata(Base):
    id: str                                    # skills/sql-analysis
    name: str
    version: str                               # semver
    description: str | None = None


class Capability(Base):
    api_version: str = API_VERSION
    kind: str = "Capability"
    metadata: CapabilityMetadata
    spec: CapabilitySpec


class ProfileComponent(Base):
    ref: str
    version: str | None = None


class ProfileSpec(Base):
    components: list[ProfileComponent] = []
    targets: list[str] = []
    deployment: DeploymentOptions | None = None


class CapabilityProfile(Base):
    api_version: str = API_VERSION
    kind: str = "CapabilityProfile"
    metadata: CapabilityMetadata
    spec: ProfileSpec


class ResolvedComponent(Base):
    ref: str
    version: str
    hash: str                                  # sha256:...
    source: str = "local"


class LockSpec(Base):
    resolved: list[ResolvedComponent] = []


class CapabilityLock(Base):
    api_version: str = API_VERSION
    kind: str = "CapabilityLock"
    metadata: CapabilityMetadata
    spec: LockSpec
```

## 内容哈希的规范化规则

**必须写死，否则跨机器哈希不一致。**

| 规则 | 取值 |
| --- | --- |
| 文件遍历 | 递归，按相对路径 POSIX 风格**字节序排序** |
| 排除 | `__pycache__/`、`*.pyc`、`.git/`、`.DS_Store`、`Thumbs.db`、`.venv/` |
| 换行归一 | 文本文件 CRLF / CR → LF |
| 编码 | UTF-8；解码失败视为二进制 |
| 二进制判定 | 含 NUL 字节或不可 UTF-8 解码 → 用原始字节，不做换行归一 |
| 是否含 `capability.yaml` | **包含**。它是资产的一部分，版本变更理应导致哈希变更 |
| 最终计算 | 逐文件算 SHA256，拼接为 `relpath\0hash\n`，再对整体算 SHA256 |

## `config.yaml`

```yaml
version: 1

# 工作区根目录；相对本文件所在目录解析
# 解析顺序：--workspace > CAPNEST_HOME > 本字段 > 当前目录
workspace: .

# 命令省略参数时的默认值
default_profile: data-agent
default_targets:
  - mcode
  - claude-code

# 部署形态：copy | symlink（Windows 需开发者模式）
deployment:
  mode: copy

# Agent 位置；缺省由 platformdirs 推断
targets:
  mcode:
    home: C:/Users/<user>/.minimax
    config_file: C:/Users/<user>/.minimax/config.yaml
  claude-code:
    home: C:/Users/<user>/.claude
    config_file: C:/Users/<user>/.claude.json
```

## 状态文件布局

```
state/
├── deployments.json        # DeploymentRecord 列表
├── ownership.json          # 路径 → 指纹
└── backups/
    └── <timestamp>/
        └── <target>/
            ├── config.yaml           # mcode 的原配置
            ├── .claude.json
            └── skills/<name>/       # 备份的目录
```

**这些文件不进 Git**。

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `CAPNEST_HOME` | 工作区根目录，覆盖 `config.yaml` |
| `CAPNEST_TARGET_HOME_<TARGET>` | 覆盖某个 target 的 home，用于测试与沙箱 |
| `NO_COLOR` | 关闭彩色输出 |

## 测试策略

| 层 | 方式 |
| --- | --- |
| 纯函数（hashing / diff / scan） | 表驱动单元测试，含跨平台固定样本 |
| 模型 | Pydantic 校验正反例 |
| Adapter | **golden fixture**：读入真实配置样本 → 归一化 → 断言结果；再用同一份样本写回 → 断言 round-trip 后除目标键外**逐字节不变** |
| 部署 | Apply → Rollback 往返测试，断言还原后与初始状态**逐字节一致** |
| 端到端 | 临时工作区 + 临时 Agent HOME，跑完整六步闭环 |
| 安全 | 隐藏 Unicode 样本库，每个类别至少一条 |

## 下一个

[004 Deployment](004-deployment.md) — 核心如何在目标 Agent 上安全地落地。
