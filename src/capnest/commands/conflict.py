"""`capnest conflict`：看分歧、裁分歧。

**冲突**= 目标侧的内容与**工作区和上次部署都不一致**。

工作区更新了不算冲突——那是「改一处，两边同步」的正路。
目标侧被外部改了才算：CapNest 不替用户决定哪一份对，
它只把分歧摆出来，并记住裁决（以工作区为准 / 以目标为准）。
裁决记在 `state/conflicts.json`，下一次 `sync` 直接照办。
"""

from __future__ import annotations

import typer

from capnest.config import DEFAULT_TARGETS
from capnest.context import AppContext, ready_workspace, use_json
from capnest.deployment.conflicts import detect_conflicts, target_path
from capnest.deployment.planning import parse_targets
from capnest.deployment.state import iso_now
from capnest.errors import NotFound, UsageError
from capnest.store.assets import AssetStore
from capnest.store.conflicts import TARGET, WORKSPACE, ConflictStore

app = typer.Typer(name="conflict", help="查看并裁决内容冲突", no_args_is_help=True)


def _targets(value: str) -> list[str]:
    names = parse_targets(value)
    return names or list(DEFAULT_TARGETS)


@app.command("list")
def list_conflicts(
    ctx: typer.Context,
    target: str = typer.Option("", "--target", help="只看某个目标，逗号分隔"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """列出全部需要裁决的分歧。"""
    context: AppContext = ctx.obj
    context.output.command = "conflict list"
    use_json(context, json_)

    workspace = ready_workspace(context)
    resolutions = ConflictStore(workspace)

    rows: list[dict[str, str]] = []
    for name in _targets(target):
        for item in detect_conflicts(workspace, name):
            decision = resolutions.find(item.asset, item.target)
            rows.append(
                {
                    **item.to_dict(),
                    "targetPath": str(target_path(name, item.name)),
                    "resolution": decision.decision if decision else "",
                    "resolvedAt": decision.at if decision else "",
                }
            )

    payload = {"conflicts": rows, "count": len(rows)}
    human = (
        "\n".join(
            f"{row['asset']:<28} {row['target']:<12} {row['kind']:<12} "
            f"{row['resolution'] or '未裁决':<12} {row['name']}"
            for row in rows
        )
        or "（没有冲突）"
    )
    context.output.success(payload, human=human)


@app.command("resolve")
def resolve_conflict(
    ctx: typer.Context,
    asset: str = typer.Argument(..., help="资产 ID，例如 skills/docx"),
    use: str = typer.Option(
        ...,
        "--use",
        help="裁决：workspace（以工作区为准）或 <target>:<name>（以目标为准）",
    ),
    target: str = typer.Option("", "--target", help="冲突发生在哪个目标上"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """裁决一个冲突。"""
    context: AppContext = ctx.obj
    context.output.command = "conflict resolve"
    use_json(context, json_)

    workspace = ready_workspace(context)
    store = AssetStore(workspace)
    resolutions = ConflictStore(workspace)

    record = store.get(asset)
    name = record.name

    if use == WORKSPACE:
        names = _targets(target)
        if not names:
            raise UsageError("请用 --target 指定冲突发生在哪个目标上")
        for item in names:
            # 认领目标路径：CapNest 从这一刻起接管它，
            # 下次同步才能合法覆盖它（归属检查要过）。
            store.claim_target_path(item, name)
            resolutions.resolve(asset, item, WORKSPACE, iso_now())
        context.output.success(
            {"asset": asset, "decision": WORKSPACE, "targets": names},
            human=f"已裁决：以工作区为准（覆盖 {', '.join(names)}）",
        )
        return

    source_target, separator, source_name = use.partition(":")
    if not separator or not source_target or not source_name:
        raise UsageError(
            "--use 的格式是 workspace 或 <target>:<name>",
            {"value": use, "example": "mcode:docx"},
        )
    if source_target not in DEFAULT_TARGETS:
        raise NotFound(
            f"未知的目标：{source_target}",
            {"target": source_target, "supported": list(DEFAULT_TARGETS)},
        )

    pulled = store.pull_from_target(asset, source_target, source_name)
    resolutions.resolve(asset, source_target, TARGET, iso_now())
    context.output.success(
        {
            "asset": asset,
            "decision": TARGET,
            "target": source_target,
            "hash": pulled.hash,
        },
        human=f"已裁决：以 {source_target} 侧为准，内容已拉回工作区",
    )
