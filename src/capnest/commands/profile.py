"""`capnest profile`：管理能力组合。

Profile 是**部署单位**——它引用哪些资产、部署到哪些目标。
"""

from __future__ import annotations

import typer

from capnest.config import DEFAULT_TARGETS, load_config
from capnest.context import AppContext, ready_workspace
from capnest.errors import NotFound, ValidationFailed
from capnest.store.assets import AssetStore
from capnest.store.profiles import ProfileStore

app = typer.Typer(name="profile", help="管理能力组合（部署单位）", no_args_is_help=True)


@app.command("create")
def create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Profile 名"),
    asset: list[str] = typer.Option([], "--asset", help="纳入 Profile 的资产 ID，可重复"),
    target: list[str] = typer.Option([], "--target", help="部署目标，可重复"),
    force: bool = typer.Option(False, "--force", help="已存在同名 Profile 时覆盖"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """新建一个 Profile。"""
    context: AppContext = ctx.obj
    context.output.command = "profile create"

    workspace = ready_workspace(context)
    store = ProfileStore(workspace)
    assets = AssetStore(workspace)

    known = {record.asset_id for record in assets.scan()}
    missing = [ref for ref in asset if ref not in known]
    if missing:
        raise NotFound(
            f"引用的资产不存在：{', '.join(missing)}",
            {"missing": missing, "known": sorted(known)},
        )

    targets = list(target)
    if not targets:
        config = load_config(workspace.config_file)
        targets = list(config.default_targets)
    unknown = [item for item in targets if item not in DEFAULT_TARGETS]
    if unknown:
        raise ValidationFailed(
            f"未知的目标：{', '.join(unknown)}",
            {"unknown": unknown, "supported": list(DEFAULT_TARGETS)},
        )

    profile = store.create(name, assets=asset, targets=targets, force=force)
    context.output.success(
        {
            "profile": profile.metadata.id,
            "path": str(store.path_for(name)),
            "components": [component.ref for component in profile.spec.components],
            "targets": list(profile.spec.targets),
        },
        human=f"已创建 Profile {profile.metadata.id} → {store.path_for(name)}",
    )


@app.command("list")
def list_profiles(
    ctx: typer.Context,
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """列出全部 Profile。"""
    context: AppContext = ctx.obj
    context.output.command = "profile list"

    workspace = ready_workspace(context)
    profiles = ProfileStore(workspace).list()
    payload = {
        "profiles": [
            {
                "id": profile.metadata.id,
                "version": profile.metadata.version,
                "components": [component.ref for component in profile.spec.components],
                "targets": list(profile.spec.targets),
            }
            for profile in profiles
        ],
        "count": len(profiles),
    }
    human = (
        "\n".join(
            f"{item['id']}  {item['version']}  {len(item['components'])} 个资产  "
            f"{', '.join(item['targets'])}"
            for item in payload["profiles"]
        )
        or "（没有 Profile）"
    )
    context.output.success(payload, human=human)


@app.command("show")
def show(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Profile 名"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """显示一个 Profile 的详情与引用资产的解析状态。"""
    context: AppContext = ctx.obj
    context.output.command = "profile show"

    workspace = ready_workspace(context)
    store = ProfileStore(workspace)
    profile = store.get(name)
    assets = AssetStore(workspace)
    known = {record.asset_id: record for record in assets.scan()}

    components = []
    for component in profile.spec.components:
        record = known.get(component.ref)
        components.append(
            {
                "ref": component.ref,
                "resolved": record is not None,
                "version": record.version if record else None,
                "hash": record.hash if record else None,
            }
        )

    payload = {
        "profile": profile.metadata.id,
        "version": profile.metadata.version,
        "description": profile.metadata.description or "",
        "components": components,
        "targets": list(profile.spec.targets),
        "path": str(store.path_for(name)),
    }
    human = (
        "\n".join(
            f"{item['ref']}  {'已解析' if item['resolved'] else '缺失'}  {item['version'] or '-'}"
            for item in components
        )
        or "（没有引用任何资产）"
    )
    context.output.success(payload, human=human)
