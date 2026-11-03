"""`capnest search`：在资产元数据上做子串匹配。

不建全文索引：资产规模是几十个量级，扫目录 + 内存过滤足够。
"""

from __future__ import annotations

import typer

from capnest.context import AppContext, ready_workspace
from capnest.store.assets import AssetStore


def _matches(record: dict[str, str], needle: str) -> bool:
    haystacks = (
        record["id"],
        record["name"],
        record["description"],
        record["type"],
    )
    return any(needle in value.lower() for value in haystacks if value)


def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="要搜的关键词"),
    type_: str = typer.Option(None, "--type", help="只搜某一类资产"),
    limit: int = typer.Option(20, "--limit", help="最多返回多少条"),
) -> None:
    """按关键词查找资产。"""
    context: AppContext = ctx.obj
    context.output.command = "search"

    workspace = ready_workspace(context)
    needle = query.strip().lower()
    records = [record.to_dict() for record in AssetStore(workspace).scan()]
    if type_:
        records = [record for record in records if record["type"] == type_]
    hits = [record for record in records if _matches(record, needle)][:limit]

    context.output.success(
        {"query": query, "assets": hits, "count": len(hits)},
        human="\n".join(f"{hit['id']}  {hit['type']}  {hit['version']}" for hit in hits)
        or "（无匹配）",
    )
