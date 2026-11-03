"""运行上下文：工作区、输出通道、配置。

输出通道遵守一条规矩：**stdout 只放结果，stderr 放诊断**。
`--json` 模式下 stdout 是纯 JSON，人类可读文本一律走 stderr；
文本模式下结果本身走 stdout。
"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from capnest.errors import CapNestError
from capnest.jsonout import error_envelope, success_envelope, write_json
from capnest.store.workspace import Workspace


@dataclass
class Output:
    """命令的输出通道。"""

    json_mode: bool = False
    color: bool = True
    command: str = "capnest"
    stdout: TextIO = field(default=sys.stdout)
    stderr: TextIO = field(default=sys.stderr)

    def success(self, data: dict[str, Any], human: str | None = None) -> None:
        """报告成功。`human` 是给人看的文本，仅在文本模式下打印。"""
        if self.json_mode:
            write_json(success_envelope(self.command, data), self.stdout)
        elif human is not None:
            self.stdout.write(human.rstrip("\n") + "\n")
            self.stdout.flush()

    def failure(self, error: CapNestError) -> None:
        """报告失败。始终使用错误 envelope 的形状。"""
        if self.json_mode:
            write_json(
                error_envelope(
                    self.command,
                    error.code,
                    error.message,
                    error.details,
                ),
                self.stdout,
            )
        else:
            self.stderr.write(f"错误 [{error.code}]：{error.message}\n")
            self.stderr.flush()

    def note(self, text: str) -> None:
        """诊断信息，永远走 stderr。"""
        if not self.json_mode:
            self.stderr.write(text.rstrip("\n") + "\n")
            self.stderr.flush()


@dataclass
class AppContext:
    """一次命令执行期间共享的东西。"""

    output: Output = field(default_factory=Output)
    workspace: Path | None = None
    config: Any = None


_CURRENT: ContextVar[AppContext | None] = ContextVar("capnest_app_context", default=None)


def set_current(context: AppContext) -> None:
    """登记当前上下文，供顶层错误处理使用。"""
    _CURRENT.set(context)


def current() -> AppContext | None:
    return _CURRENT.get()


def workspace_of(context: AppContext) -> Workspace:
    """解析并缓存当前上下文的工作区。"""
    if context.workspace is None:
        from capnest.config import resolve_workspace

        context.workspace = resolve_workspace(None)
    return Workspace(context.workspace)


def ready_workspace(context: AppContext) -> Workspace:
    """解析工作区并确认它**已经初始化**。

    除 `init` 外的所有命令都走这里：工作区不存在或没有 `config.yaml`
    一律报 NOT_FOUND（退出码 8），而不是在半个工作区上继续操作。
    """
    from capnest.config import require_initialized

    workspace = workspace_of(context)
    require_initialized(workspace.root)
    return workspace


def use_json(context: AppContext, flag: bool) -> None:
    """命令级的 `--json` 打开 JSON 输出。

    `--json` 是全局选项（放在子命令之前），但 `capnest list --json` 也是
    极常见的写法——两种都支持，命令级的开关优先级更高。
    """
    if flag:
        context.output.json_mode = True
