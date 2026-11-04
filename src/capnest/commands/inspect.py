"""`capnest inspect <target>`：看目标 Agent 侧现在有什么。

这是「收编」的前置一步——要先知道目标里有哪些 skill、叫什么名字、
CapNest 管不管它，才谈得上 `add --from <target>:<name>`。

**只读**：不写任何文件，不改任何归属。
"""

from __future__ import annotations

import typer

from capnest.adapters import known_targets, make_adapter
from capnest.context import AppContext, use_json
from capnest.deployment.ownership import OwnershipRegistry
from capnest.errors import NotFound
from capnest.store.workspace import Workspace


def _render(rows: list[dict[str, object]], target: str, path: str) -> str:
    """人类可读的盘点表。"""
    if not rows:
        return f"{target} 侧没有任何 skill（{path}）"
    header = ("SKILL", "FILES", "HASH", "STATE")
    body = [
        (
            str(row["name"]),
            str(row["files"]),
            str(row["hash"])[:20],
            str(row["state"]),
        )
        for row in rows
    ]
    widths = [max(len(header[index]), *(len(line[index]) for line in body)) for index in range(4)]
    lines = [f"{target}  ({path})"]
    lines.append("  ".join(header[index].ljust(widths[index]) for index in range(4)))
    for line in body:
        lines.append("  ".join(line[index].ljust(widths[index]) for index in range(4)))
    lines.append("")
    lines.append(f"收编其中一份：capnest add --from {target}:<名字>")
    return "\n".join(lines)


def inspect(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="要查看的目标：mcode / claude-code"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """列出目标 Agent 侧已有的 skill。"""
    context: AppContext = ctx.obj
    context.output.command = "inspect"
    use_json(context, json_)

    if target not in known_targets():
        raise NotFound(
            f"未知的目标：{target}",
            {"target": target, "supported": list(known_targets())},
        )

    adapter = make_adapter(target)
    state = adapter.read()

    workspace: Workspace | None = None
    try:
        from capnest.context import workspace_of

        workspace = workspace_of(context)
    except Exception:  # pragma: no cover - 工作区不可用时只报目标侧
        workspace = None

    registry = (
        OwnershipRegistry(workspace.ownership_file)
        if workspace is not None and workspace.ownership_file.is_file()
        else None
    )

    rows: list[dict[str, object]] = []
    for name in sorted(state.skills):
        path = adapter.skill_path(name)
        files = sum(1 for item in path.rglob("*") if item.is_file())
        has_manifest = (path / "SKILL.md").is_file()
        if registry is not None and registry.owned_by_us(path):
            state_text = "managed"
        elif name in state.nested:
            state_text = "nested"
        elif not has_manifest:
            state_text = "container"
        else:
            state_text = "unmanaged"
        rows.append(
            {
                "name": name,
                "files": files,
                "hash": state.skills[name],
                "state": state_text,
                "nested": name in state.nested,
                "has_manifest": has_manifest,
                "path": str(path),
            }
        )

    payload = {
        "target": target,
        "skills_path": str(adapter.skills_path),
        "skills": rows,
        "count": len(rows),
    }
    context.output.success(
        payload,
        human=_render(rows, target, str(adapter.skills_path)),
    )
