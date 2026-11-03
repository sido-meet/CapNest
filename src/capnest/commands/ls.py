"""`capnest list`：列出工作区里的全部资产。"""

from __future__ import annotations

import typer

from capnest.context import AppContext, ready_workspace
from capnest.store.assets import AssetStore

#: `--sort` 的可选值。
SORT_KEYS = ("id", "type", "version", "name")


def _render(records: list[dict[str, str]]) -> str:
    """人类可读输出。对齐成三列，不依赖终端的表格能力。"""
    if not records:
        return "（没有资产）"
    header = ("ID", "TYPE", "VERSION", "HASH")
    rows = [
        (
            record["id"],
            record["type"],
            record["version"],
            record["hash"][:20],
        )
        for record in records
    ]
    widths = [max(len(header[index]), *(len(row[index]) for row in rows)) for index in range(4)]
    lines = ["  ".join(header[index].ljust(widths[index]) for index in range(4))]
    for row in rows:
        lines.append("  ".join(row[index].ljust(widths[index]) for index in range(4)))
    return "\n".join(lines)


def ls(
    ctx: typer.Context,
    type_: str = typer.Option(None, "--type", help="只列出某一类资产"),
    sort: str = typer.Option("id", "--sort", help=f"排序字段：{' / '.join(SORT_KEYS)}"),
) -> None:
    """列出全部资产。"""
    context: AppContext = ctx.obj
    context.output.command = "list"

    workspace = ready_workspace(context)
    records = [record.to_dict() for record in AssetStore(workspace).scan()]

    if type_:
        records = [record for record in records if record["type"] == type_]
    if sort in SORT_KEYS:
        records.sort(key=lambda record: record[sort])

    context.output.success(
        {"assets": records, "count": len(records)},
        human=_render(records),
    )
