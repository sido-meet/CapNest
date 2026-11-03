"""`capnest status`：目标侧现状与 CapNest 记录的对照。

两种检测**分开报**：

- **drift**——目标侧被外部改了（目标内容哈希 ≠ 部署时的资产哈希）；
- **version-lag**——CapNest 里的资产更新了（工作区资产哈希 ≠ 部署时的资产哈希）。
"""

from __future__ import annotations

import typer

from capnest.adapters import make_adapter
from capnest.context import AppContext, ready_workspace, use_json
from capnest.deployment.planning import parse_targets
from capnest.deployment.state import DeploymentStore
from capnest.errors import DriftDetected
from capnest.hashing import hash_dir
from capnest.store.assets import AssetStore


def status(
    ctx: typer.Context,
    profile: str = typer.Option(None, "--profile", help="只看这个 Profile"),
    target: str = typer.Option("", "--target", help="目标，逗号分隔"),
    strict: bool = typer.Option(False, "--strict", help="有漂移或版本落后时以退出码 4 结束"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """汇报每个目标的部署状态。"""
    context: AppContext = ctx.obj
    context.output.command = "status"
    use_json(context, json_)

    workspace = ready_workspace(context)
    store = DeploymentStore(workspace.deployments_file)
    records = store.load()

    names = parse_targets(target)
    if not names:
        names = sorted({record.target for record in records})
    if profile:
        records = [record for record in records if record.profile == profile]
        names = [
            name
            for name in names
            if any(record.target == name and record.profile == profile for record in records)
        ]

    assets = {record.asset_id: record for record in AssetStore(workspace).scan()}
    rows: list[dict[str, str]] = []

    for name in names:
        candidates = [
            record
            for record in records
            if record.target == name and (not profile or record.profile == profile)
        ]
        if not candidates:
            rows.append(
                {
                    "target": name,
                    "profile": profile or "-",
                    "status": "never-deployed",
                    "detail": "",
                }
            )
            continue
        record = max(candidates, key=lambda item: item.created_at)
        adapter = make_adapter(name)

        drift: list[str] = []
        lag: list[str] = []
        for asset_id, deployed_hash in record.asset_hashes.items():
            asset_name = asset_id.rsplit("/", 1)[-1]
            target_dir = adapter.skill_path(asset_name)
            if not target_dir.is_dir():
                drift.append(f"{asset_name} 缺失")
                continue
            if hash_dir(target_dir) != deployed_hash:
                drift.append(f"{asset_name} 被外部修改")
            current = assets.get(asset_id)
            if current is not None and current.hash != deployed_hash:
                lag.append(f"{asset_name} {deployed_hash[:16]} → {current.hash[:16]}")

        if drift:
            state, detail = "drift", "；".join(drift)
        elif lag:
            state, detail = "version-lag", "；".join(lag)
        else:
            state, detail = "up-to-date", ""
        rows.append(
            {
                "target": name,
                "profile": record.profile,
                "status": state,
                "detail": detail,
                "deployment": record.id,
            }
        )

    payload = {"targets": rows}
    human = (
        "\n".join(
            f"{row['target']:<12} {row['profile']:<12} {row['status']:<14} {row['detail']}"
            for row in rows
        )
        or "（没有部署记录）"
    )
    context.output.success(payload, human=human)

    problems = [row for row in rows if row["status"] in ("drift", "version-lag")]
    if strict and problems:
        raise DriftDetected(
            f"{len(problems)} 个目标存在漂移或版本落后",
            {"targets": problems},
        )
