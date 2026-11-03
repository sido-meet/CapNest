"""`capnest validate`：检查工作区里的资产与 Profile。"""

from __future__ import annotations

import typer

from capnest.context import AppContext, ready_workspace, use_json
from capnest.errors import ValidationFailed
from capnest.store.assets import AssetStore
from capnest.store.profiles import ProfileStore
from capnest.validation import validate_workspace


def validate(
    ctx: typer.Context,
    asset: str = typer.Option(None, "--asset", help="只校验一个资产 ID"),
    strict: bool = typer.Option(False, "--strict", help="把 warn 升级为 error"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """跑完整校验。"""
    context: AppContext = ctx.obj
    context.output.command = "validate"
    use_json(context, json_)

    workspace = ready_workspace(context)
    records = AssetStore(workspace).scan()
    profiles = ProfileStore(workspace).list()

    violations = validate_workspace(records, profiles, strict=strict, only=asset)
    errors = [item for item in violations if item.level == "error"]
    warnings = [item for item in violations if item.level == "warn"]

    payload = {
        "violations": [item.to_dict() for item in violations],
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checked_assets": len(records) if not asset else 1,
        "checked_profiles": len(profiles) if not asset else 0,
    }

    if errors:
        raise ValidationFailed(
            f"校验未通过：{len(errors)} 个 error",
            payload,
        )

    human = (
        "\n".join(
            f"{item.level:>5}  {item.asset}  {item.location}  {item.message}" for item in violations
        )
        or "（一切正常）"
    )
    context.output.success(payload, human=human)
