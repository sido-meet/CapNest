"""`capnest add`：把一个能力登记进工作区。

两条路径：

- `add <kind> <PATH>`——从本地目录导入；
- `add --from <target>:<name>`——从 Agent 侧**收编**既有能力，原文件不动。
"""

from __future__ import annotations

from pathlib import Path

import typer

from capnest.context import AppContext, ready_workspace, use_json
from capnest.errors import UsageError
from capnest.store.assets import AssetStore


def add(
    ctx: typer.Context,
    kind: str = typer.Argument(None, help="资产类型：skill / mcp / workflow"),
    path: Path = typer.Argument(None, help="源目录"),
    name: str = typer.Option(None, "--name", help="资产名，缺省用目录名"),
    force: bool = typer.Option(False, "--force", help="已存在同名资产时覆盖"),
    from_: str = typer.Option(None, "--from", help="从某个 Agent 收编：<target>:<name>"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """导入或收编一个能力。"""
    context: AppContext = ctx.obj
    context.output.command = "add"
    use_json(context, json_)

    workspace = ready_workspace(context)
    store = AssetStore(workspace)

    if from_:
        target, separator, asset_name = from_.partition(":")
        if not separator or not target or not asset_name:
            raise UsageError(
                "--from 的格式是 <target>:<name>",
                {"value": from_, "example": "mcode:manim"},
            )
        record = store.adopt_from_target(target, asset_name, force=force)
    else:
        if not kind or path is None:
            raise UsageError(
                "用法：capnest add <kind> <PATH> 或 capnest add --from <target>:<name>",
                {"kind": kind, "path": str(path) if path else None},
            )
        record = store.import_path(path, kind, name=name, force=force)

    context.output.success(
        record.to_dict(),
        human=f"已登记 {record.asset_id}（{record.version}）→ {record.path}",
    )
