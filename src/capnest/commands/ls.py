"""`capnest list`：列出工作区里的全部资产。"""

from __future__ import annotations

import typer

from capnest.context import AppContext, ready_workspace, use_json
from capnest.store.assets import AssetStore

#: `--sort` 的可选值。
SORT_KEYS = ("id", "type", "version", "name", "source")

#: 目标 id → 给人看的名字。
TARGET_DISPLAY: dict[str, str] = {
    "mcode": "mcode",
    "claude-code": "Claude Code",
}


def source_label(record: dict[str, str]) -> str:
    """资产的来源标签。本地创建的标 `local`；多处都有就都列出来。"""
    labels = _source_labels(record)
    if not labels:
        return "local"
    return " + ".join(labels)


def _render(records: list[dict[str, str]]) -> str:
    """人类可读输出。对齐成几列，不依赖终端的表格能力。"""
    if not records:
        return "（没有资产）"
    header = ("ID", "TYPE", "VERSION", "SOURCE", "HASH")
    rows = [
        (
            record["id"],
            record["type"],
            record["version"],
            source_label(record),
            record["hash"][:20],
        )
        for record in records
    ]
    widths = [max(len(header[index]), *(len(row[index]) for row in rows)) for index in range(5)]
    lines = ["  ".join(header[index].ljust(widths[index]) for index in range(5))]
    for row in rows:
        lines.append("  ".join(row[index].ljust(widths[index]) for index in range(5)))
    return "\n".join(lines)


def _source_labels(record: dict[str, str]) -> list[str]:
    """一个资产的**各个**来源标签（去重，保持顺序）。"""
    sources = record.get("sources") or []
    if not sources:
        source = record.get("source") or {}
        sources = [source] if source.get("target") else []
    labels: list[str] = []
    for item in sources:
        target = item.get("target") or ""
        label = TARGET_DISPLAY.get(target, target)
        if label and label not in labels:
            labels.append(label)
    return labels


def ls(
    ctx: typer.Context,
    type_: str = typer.Option(None, "--type", help="只列出某一类资产"),
    sort: str = typer.Option("id", "--sort", help=f"排序字段：{' / '.join(SORT_KEYS)}"),
    source: str = typer.Option(None, "--source", help="只列出某个来源的资产"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """列出全部资产。"""
    context: AppContext = ctx.obj
    context.output.command = "list"
    use_json(context, json_)

    workspace = ready_workspace(context)
    records = [record.to_dict() for record in AssetStore(workspace).scan()]

    if type_:
        records = [record for record in records if record["type"] == type_]
    if source:
        records = [
            record
            for record in records
            if source in _source_labels(record) or source_label(record) == source
        ]
    if sort in SORT_KEYS:
        records.sort(key=lambda record: (record[sort], record["id"]))

    context.output.success(
        {"assets": records, "count": len(records)},
        human=_render(records),
    )
