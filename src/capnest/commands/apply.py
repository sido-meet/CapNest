"""`capnest apply`：把 Profile 部署到目标。

完整流程：**扫描 → 归属 → 事务 → 确认 → 提交 → 记录**。

任何一步失败都不留下半成品——要么没写，要么写完整。
"""

from __future__ import annotations

import typer

from capnest.context import AppContext, ready_workspace, use_json
from capnest.deployment.atomic import AtomicWriter, WriteIntent
from capnest.deployment.backup import BackupStore
from capnest.deployment.diff import CREATE, UPDATE
from capnest.deployment.planning import TargetPlan, build_plans, parse_targets
from capnest.deployment.state import DeploymentRecord, DeploymentStore, iso_now, timestamp_now
from capnest.errors import ConfirmationRequired, Conflict, UnsafeContent, UsageError
from capnest.hashing import hash_dir
from capnest.security.scan import scan_tree
from capnest.store.workspace import Workspace


def _writable(plan: TargetPlan) -> list[tuple]:
    """（资产, diff）二元组，只取真的要写的。"""
    by_name = {diff.name: diff for diff in plan.diffs}
    items: list[tuple] = []
    for asset in plan.plan.assets:
        diff = by_name.get(asset.name)
        if diff is None or diff.status not in (CREATE, UPDATE):
            continue
        items.append((asset, diff))
    return items


def _scan_assets(plans: list[TargetPlan]) -> None:
    """隐藏 Unicode 扫描：命中即阻断。"""
    findings = []
    for plan in plans:
        for asset in plan.plan.assets:
            for finding in scan_tree(asset.path):
                findings.append({**finding.to_dict(), "asset": asset.asset_id})
    if findings:
        raise UnsafeContent(
            f"检测到 {len(findings)} 处隐藏 Unicode 字符，已阻断",
            {"findings": findings},
        )


def _check_ownership(workspace: Workspace, plans: list[TargetPlan]) -> None:
    """归属检查：证明不了的既有路径一律拒绝。"""
    from capnest.deployment.ownership import OwnershipRegistry

    registry = OwnershipRegistry(workspace.ownership_file)
    conflicts: list[dict] = []
    for plan in plans:
        for asset, _ in _writable(plan):
            path = plan.adapter.skill_path(asset.name)
            try:
                registry.check(path)
            except Conflict as exc:
                conflicts.append({**exc.details, "target": plan.target, "asset": asset.asset_id})
    if conflicts:
        raise Conflict(
            f"有 {len(conflicts)} 个目标路径无法证明归属，拒绝写入",
            {"conflicts": conflicts},
        )


def deploy(
    workspace: Workspace,
    plans: list[TargetPlan],
    *,
    yes: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    """执行一次部署。`apply` 与 `sync` 共用这一段——两边看到的必须是同一套规则。"""
    _scan_assets(plans)
    _check_ownership(workspace, plans)

    pending = [(plan, asset, diff) for plan in plans for asset, diff in _writable(plan)]

    if dry_run:
        return {
            "dry_run": True,
            "targets": [item.to_dict() for item in plans],
            "would_write": [
                {"target": plan.target, "asset": asset.asset_id, "status": diff.status}
                for plan, asset, diff in pending
            ],
        }

    if pending and not yes:
        raise ConfirmationRequired(
            f"将写入 {len(pending)} 个 skill；确认执行请加 --yes",
            {
                "would_write": [
                    {
                        "target": plan.target,
                        "asset": asset.asset_id,
                        "status": diff.status,
                        "path": str(plan.adapter.skill_path(asset.name)),
                    }
                    for plan, asset, diff in pending
                ]
            },
        )

    timestamp = timestamp_now()
    backups = BackupStore(workspace.backups_dir)
    writers: list[tuple[TargetPlan, AtomicWriter]] = []
    transactions = []
    intents_by_plan: dict[str, list[WriteIntent]] = {}

    for plan in plans:
        intents = [
            WriteIntent(
                source=asset.path,
                target=plan.adapter.skill_path(asset.name),
                action=diff.status,
                asset_id=asset.asset_id,
                name=asset.name,
            )
            for asset, diff in _writable(plan)
        ]
        if not intents:
            continue
        plan.adapter.skills_path.mkdir(parents=True, exist_ok=True)
        writer = AtomicWriter(backups, timestamp, plan.target)
        writers.append((plan, writer))
        intents_by_plan[plan.target] = intents

    # 先全部 stage，再逐个提交；任何一个提交失败，其余全部回滚。
    try:
        for plan, writer in writers:
            transactions.append((plan, writer, writer.stage(intents_by_plan[plan.target])))
        for _plan, writer, transaction in transactions:
            writer.commit(transaction)
    except BaseException:
        for _plan, writer, transaction in transactions:
            writer.abort(transaction)
        raise

    registry = _ownership_registry(workspace)
    store = DeploymentStore(workspace.deployments_file)
    records = store.load()
    created_at = iso_now()
    applied: list[dict] = []

    for plan, _writer, transaction in transactions:
        for intent in transaction.intents:
            registry.claim(intent.target, hash_dir(intent.target))
        record = DeploymentRecord(
            id=f"{timestamp}-{plan.target}",
            profile=plan.plan.profile,
            target=plan.target,
            created_at=created_at,
            mode=str(plan.plan.mode),
            applied_paths=[str(plan.adapter.skill_path(item.name)) for item in plan.plan.assets],
            backups=dict(transaction.backups),
            created_paths=list(transaction.created),
            asset_hashes={item.asset_id: item.hash for item in plan.plan.assets},
        )
        records.append(record)
        applied.append(
            {
                "target": plan.target,
                "profile": plan.plan.profile,
                "deployment": record.id,
                "paths": record.applied_paths,
                "created": record.created_paths,
            }
        )
    registry.save()
    store.save(records)

    return {"applied": applied, "timestamp": timestamp}


def apply(
    ctx: typer.Context,
    profile: str = typer.Option(None, "--profile", help="Profile 名"),
    target: str = typer.Option("", "--target", help="目标，逗号分隔"),
    yes: bool = typer.Option(False, "--yes", help="确认执行，不必交互"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只做前置校验，不写任何文件"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """部署一个 Profile。"""
    context: AppContext = ctx.obj
    context.output.command = "apply"
    use_json(context, json_)

    workspace = ready_workspace(context)
    names = parse_targets(target)
    if not names:
        from capnest.config import load_config

        names = list(load_config(workspace.config_file).default_targets)
    if not names:
        raise UsageError("没有可用的目标，请用 --target 指定")

    plans = build_plans(workspace, profile, names)
    result = deploy(workspace, plans, yes=yes, dry_run=dry_run)

    if dry_run:
        context.output.success(
            result,
            human=f"预演通过：将写入 {len(result['would_write'])} 个 skill",
        )
        return
    context.output.success(
        result,
        human=f"已部署 {len(result['applied'])} 个目标",
    )


def _ownership_registry(workspace: Workspace):
    from capnest.deployment.ownership import OwnershipRegistry

    return OwnershipRegistry(workspace.ownership_file)
