"""`capnest plan`：预览将要发生的变更。

**只读**——不写任何文件，连日志都不写。
"""

from __future__ import annotations

import typer

from capnest.context import AppContext, ready_workspace, use_json
from capnest.deployment.diff import EXTRA, UNCHANGED
from capnest.deployment.planning import build_plans, parse_targets
from capnest.errors import UsageError

#: v1 不支持删除目标上多出来的文件。
REMOVAL_NOTE = "[skipped: removal not supported in v1]"


def _render(plans: list) -> str:
    """人类可读的计划。"""
    lines: list[str] = []
    for plan in plans:
        lines.append(plan.target)
        for diff in plan.diffs:
            marker = {"create": "+", "update": "~", "unchanged": "="}[diff.status]
            lines.append(f"  {marker} {diff.name}/  ({diff.status})")
            for item in diff.files:
                if item.action == EXTRA:
                    lines.append(f"    - {item.path}  {REMOVAL_NOTE}")
                elif item.action == UNCHANGED:
                    lines.append(f"    = {item.path}")
                else:
                    lines.append(f"    {item.action[0].upper()} {item.path}")
        for note in plan.plan.skipped:
            lines.append(f"  {note}")
    if not plans:
        return "（没有目标）"
    return "\n".join(lines)


def plan(
    ctx: typer.Context,
    profile: str = typer.Option(None, "--profile", help="Profile 名"),
    target: str = typer.Option("", "--target", help="目标，逗号分隔"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """计算并展示将要发生的变更，不写任何文件。"""
    context: AppContext = ctx.obj
    context.output.command = "plan"
    use_json(context, json_)

    workspace = ready_workspace(context)
    names = parse_targets(target)
    if not names:
        from capnest.config import load_config

        names = list(load_config(workspace.config_file).default_targets)
    if not names:
        raise UsageError("没有可用的目标，请用 --target 指定")

    plans = build_plans(workspace, profile, names)
    payload = {"targets": [item.to_dict() for item in plans]}
    context.output.success(payload, human=_render(plans))
