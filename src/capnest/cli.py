"""命令行入口。

全局选项放在**子命令之前**：`capnest --workspace ./ws --json add skill ./x`。
所有命令都通过 Typer 注册，业务逻辑在 `commands/` 与各子系统里。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from capnest import __version__
from capnest.context import AppContext, Output, set_current, workspace_of
from capnest.errors import CapNestError
from capnest.store.workspace import Workspace

app = typer.Typer(
    name="capnest",
    help="Personal Capability Infrastructure：一次维护，跨 Agent 部署出完全相同的一份能力。",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _show_version(value: bool) -> None:
    """`--version` 是即时选项：不等子命令，直接打印并退出。"""
    if value:
        typer.echo(f"capnest {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    ctx: typer.Context,
    json_mode: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
    workspace: Path | None = typer.Option(None, "--workspace", help="工作区根目录"),
    no_color: bool = typer.Option(False, "--no-color", help="关闭彩色输出"),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_show_version,
        is_eager=True,
        help="显示版本并退出",
    ),
) -> None:
    """CapNest 的全局选项。"""
    color = not no_color and not os.environ.get("NO_COLOR")
    context = AppContext(
        output=Output(json_mode=json_mode, color=color),
        workspace=workspace.expanduser().resolve() if workspace is not None else None,
    )
    set_current(context)
    ctx.obj = context


def workspace_from(ctx: typer.Context) -> Workspace:
    """解析当前命令使用的工作区（并缓存到上下文里）。"""
    return workspace_of(ctx.obj)


def register_commands() -> None:
    """注册全部命令。拆开是为了让 `cli.py` 只剩装配逻辑。"""
    from capnest.commands import init

    app.command("init")(init.init)


def main(argv: list[str] | None = None) -> None:
    """进程入口：把异常翻译成错误 envelope 与退出码。"""
    command = typer.main.get_command(app)
    try:
        result = command.main(args=argv, standalone_mode=False)
    except CapNestError as exc:
        context = _current_context()
        if context is None:
            sys.stderr.write(f"错误 [{exc.code}]：{exc.message}\n")
        else:
            context.output.failure(exc)
        raise SystemExit(exc.exit_code) from None
    except Exception as exc:
        # Typer 0.27 把 click 内联为 typer._click，不再是公开依赖，
        # 因此这里按鸭子类型识别 click 风格的异常，不引用私有模块。
        if exc.__class__.__name__ == "Abort":
            sys.stderr.write("已中止\n")
            raise SystemExit(1) from None
        code = getattr(exc, "exit_code", None)
        if isinstance(code, int):
            show = getattr(exc, "show", None)
            if callable(show):
                show()
            raise SystemExit(code) from None
        raise
    # click 在 standalone_mode=False 下会吞掉 Exit 并把退出码作为返回值，
    # 所以命令返回整数即代表退出码（本项目的命令一律返回 None）。
    if isinstance(result, int):
        raise SystemExit(result)


def _current_context() -> AppContext | None:
    from capnest.context import current

    return current()


register_commands()


if __name__ == "__main__":  # pragma: no cover
    main()
