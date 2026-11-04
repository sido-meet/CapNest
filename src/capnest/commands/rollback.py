"""`capnest rollback`：把某个目标恢复到最近一次部署之前。

只动 CapNest 记录过的路径：备份还原、新建路径删除、归属释放、记录移除。
用户在 Agent 侧手工改过、且 CapNest 没有备份的内容**不动**——那属于漂移，
应该由用户自己决定。
"""

from __future__ import annotations

from pathlib import Path

import typer

from capnest.context import AppContext, ready_workspace, use_json
from capnest.deployment.backup import BackupStore
from capnest.deployment.ownership import OwnershipRegistry
from capnest.deployment.state import DeploymentStore
from capnest.errors import NotFound, UsageError
from capnest.util.fs import remove_tree


def rollback(
    ctx: typer.Context,
    target: str = typer.Option("", "--target", help="要回滚的目标"),
    yes: bool = typer.Option(
        False, "--yes", help="确认执行（第一刀不需要，回滚只动 CapNest 记录过的路径）"
    ),
    to: str = typer.Option(None, "--to", help="回滚到指定的部署记录 ID"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """回滚一次部署。"""
    context: AppContext = ctx.obj
    context.output.command = "rollback"
    use_json(context, json_)

    workspace = ready_workspace(context)
    store = DeploymentStore(workspace.deployments_file)

    if to:
        record = store.find(to)
        if record is None:
            raise NotFound(f"部署记录不存在：{to}", {"deployment": to})
    else:
        if not target:
            raise UsageError("请用 --target 或 --to 指定要回滚的部署")
        record = store.latest_for(target)
        if record is None:
            raise NotFound(
                f"目标 {target} 没有可回滚的部署记录",
                {"target": target},
            )

    backups = BackupStore(workspace.backups_dir)
    restored: list[str] = []
    removed: list[str] = []

    for target_path, ref in record.backups.items():
        source = backups.resolve(ref)
        if not source.exists():
            continue
        backups.restore(ref, Path(target_path))
        restored.append(target_path)

    for created in record.created_paths:
        path = Path(created)
        if path.exists():
            remove_tree(path)
            removed.append(created)

    # 目标 skills 目录如果是这次部署创建出来的，回滚后它应该消失。
    # 只在**完全为空**时删除——空目录里没有任何用户数据。
    try:
        from capnest.adapters import make_adapter

        skills_dir = make_adapter(record.target).skills_path
        if skills_dir.is_dir() and not any(skills_dir.iterdir()):
            skills_dir.rmdir()
    except OSError:
        pass

    registry = OwnershipRegistry(workspace.ownership_file)
    for applied in record.applied_paths:
        registry.release(Path(applied))
    registry.save()

    store.remove(record.id)

    context.output.success(
        {
            "deployment": record.id,
            "target": record.target,
            "profile": record.profile,
            "restored": restored,
            "removed": removed,
        },
        human=f"已回滚 {record.id}：还原 {len(restored)} 个路径，删除 {len(removed)} 个新建路径",
    )
