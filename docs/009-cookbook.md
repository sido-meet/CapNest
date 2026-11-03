# 009 Cookbook

本文是操作手册：如何新增一个部署目标。

## 前置

一个目标（target）指一个 CapNest 可以写入的 Agent。新增目标需要回答四个问题：

1. 它的能力放在哪个目录？
2. 它的 MCP 配置在哪个文件、哪个键？
3. 那个文件能不能被安全地局部改写？
4. 它支持哪些资产类型与部署形态？

四个问题都有答案之后，写代码。

## 步骤

### 1. 实测目标格式

用环境变量把 Agent 的配置目录指向临时目录，重复「新增一个 MCP Server」「新增一个 Skill」，观察它实际写了什么。

**不要凭文档或记忆写 Adapter。** 目标 Agent 的配置格式是本仓库里唯一容易过期的东西，必须以实测为准，并落成 fixture 样本。

### 2. 抓样本

把实测后的配置文件放进 `tests/fixtures/`，命名 `<target>_config.<ext>`。它是 golden fixture 测试的输入，也是其他人的事实来源。

### 3. 实现 Adapter

新建 `src/capnest/adapters/<target>.py`，实现 [005 Adapters](005-adapters.md) 的协议：

```python
class Adapter(Protocol):
    target: str
    def capabilities(self) -> TargetCapabilities: ...
    def read(self) -> TargetState: ...
    def plan(self, desired: DesiredState) -> list[WriteIntent]: ...
    def verify(self, expected: TargetState) -> VerificationResult: ...
```

四个方法的边界：

| 方法 | 做什么 | 不做什么 |
| --- | --- | --- |
| `capabilities` | 声明支持的资产类型、部署形态、skills 路径、MCP 后端格式 | 不做版本决策 |
| `read` | 读目标现状并归一化成 `TargetState` | 不写任何文件 |
| `plan` | 产出 `WriteIntent` 列表（只新增/更新） | 不落盘，不做归属判断 |
| `verify` | 校验写回结果 | 不做 diff |

在 `src/capnest/adapters/__init__.py` 的注册表里登记。

### 4. 写清楚怎么局部改写

共享配置文件（mcode 的 `config.yaml`、Claude Code 的 `.claude.json`）**不能整体重写**。Adapter 必须实现定点编辑：

1. 读原文为字符串
2. 定位目标键的块边界
3. 只在块内 upsert
4. 用新块替换原文区间，其余字节逐字保留

写前检查 mtime 与读取时是否一致，不一致就中止。

写后做 diff 校验：只允许目标键相关的行变化，出现任何预期外变化即中止并报错。

### 5. 归一化 MCP 定义

把目标格式映射到 `McpServerDef`（`transport` / `command` / `args` / `env` / `url` / `headers`）。密钥不落明文：资产里写 `${ENV_VAR}`，部署时解析，未定义则报错中止。

### 6. 补测试

- **读**：fixture → 归一化 → 断言 `TargetState` 每一项
- **写**：fixture → 写回 → 断言除目标键外**逐字节不变**
- **往返**：读 → 写 → 再读 → 归一化结果相同

### 7. 接入 `doctor`

`doctor` 需要报告这个 target 的能力矩阵（支持哪些资产类型与部署形态、skills 路径、MCP 后端格式）。[006 CLI](006-cli.md) 里有 `doctor` 的输出结构。

### 8. 补文档

- 在 [005 Adapters](005-adapters.md) 增加该目标的格式说明与实测结论
- 在 [001 Domain model](001-domain.md) 的目标列表中登记
- 在 [007 Tasks](007-tasks.md) 增加对应的任务并勾选

## 检查清单

| # | 检查项 |
| --- | --- |
| 1 | 配置格式来自实测，且有 fixture 样本 |
| 2 | `read` 不写文件 |
| 3 | `plan` 只产出新增/更新 |
| 4 | 共享文件走定点编辑，其余字节逐字保留 |
| 5 | 写前 mtime 检查、写后 diff 校验 |
| 6 | 密钥只以 `${ENV_VAR}` 形式出现 |
| 7 | golden fixture 测试：读、写、往返三项 |
| 8 | `doctor` 报告能力矩阵 |
| 9 | 文档已更新 |