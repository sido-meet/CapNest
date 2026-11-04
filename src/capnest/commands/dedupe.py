"""`capnest dedupe`：找重复。

**重复**有两层，含义完全不同：

| 情形 | 判定 | 处理 |
| --- | --- | --- |
| 同名同内容 | 同一份能力在两个 Agent 侧都有 | 收编时自动去重——只保留一份，来源合并 |
| 同内容不同名 | 同一份能力被放进了两个名字 | **只报告，不自动合并**——名字不同往往是有意的 |

第二类不自动动手：两个名字可能各有用意，合并掉哪一个是用户的事。
"""

from __future__ import annotations

import typer

from capnest.context import AppContext, ready_workspace, use_json
from capnest.store.assets import AssetStore


def dedupe(
    ctx: typer.Context,
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """列出内容相同、名字不同的资产组。"""
    context: AppContext = ctx.obj
    context.output.command = "dedupe"
    use_json(context, json_)

    workspace = ready_workspace(context)
    groups = AssetStore(workspace).find_duplicates()

    payload = {"groups": groups, "count": len(groups)}
    human = (
        "\n".join(f"{'  =  '.join(group['names'])}  （{group['hash'][:20]}）" for group in groups)
        or "（没有重复）"
    )
    context.output.success(payload, human=human)
