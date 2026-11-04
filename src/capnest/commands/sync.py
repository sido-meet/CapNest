"""`capnest sync`：一次把两边的能力收成一份，再同步回去。

这是第一刀真正想解决的那件事的操作入口：

```
收编（可选）→ 去重 → 冲突 → 同步
```

四步各自都有明确的边界：

1. **收编**：把两个 Agent 侧已有的 skill 复制进工作区——原文件一个字节不动。
   同名同内容自动去重（只保留一份，来源合并）；同名不同内容记成冲突，不覆盖。
2. **去重**：内容相同、名字不同的资产只报告，不自动合并。
3. **冲突**：工作区与目标侧内容不同。没有裁决的冲突**不写**那个目标，
   其余照常同步——一处分歧不该拖住全局。
4. **同步**：把工作区里的资产写回每个目标。写之前照旧做归属检查：
   证明不了归属的既有路径一律拒绝。

同步是**幂等**的：内容一样就不写，重复执行不会动 mtime。
"""

from __future__ import annotations

import typer

from capnest.adapters import make_adapter
from capnest.config import load_config
from capnest.context import AppContext, ready_workspace, use_json
from capnest.deployment.ownership import OwnershipRegistry
from capnest.deployment.planning import build_plans_for, parse_targets
from capnest.errors import Conflict
from capnest.models import CapabilityType
from capnest.store.assets import AssetStore, content_hash
from capnest.store.conflicts import WORKSPACE, ConflictStore
from capnest.store.profiles import ProfileStore, make_profile


def sync(
    ctx: typer.Context,
    target: str = typer.Option("", "--target", help="目标，逗号分隔"),
    adopt: bool = typer.Option(False, "--adopt", help="先把目标侧已有的 skill 收编进来"),
    profile: str = typer.Option(None, "--profile", help="只同步这个 Profile 里的资产"),
    yes: bool = typer.Option(False, "--yes", help="确认执行，不必交互"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只做前置校验，不写任何文件"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """收编 → 去重 → 冲突 → 同步。"""
    context: AppContext = ctx.obj
    context.output.command = "sync"
    use_json(context, json_)

    workspace = ready_workspace(context)
    store = AssetStore(workspace)
    resolutions = ConflictStore(workspace)

    names = parse_targets(target)
    if not names:
        names = list(load_config(workspace.config_file).default_targets)
    if not names:
        raise Conflict("没有可用的目标，请用 --target 指定", {"targets": names})

    # ---------------------------------------------------------------- 收编
    adoption: dict[str, object] = {}
    if adopt:
        adoption = store.adopt_all_from_targets(names)

    # ---------------------------------------------------------------- 资产集合
    records = store.scan()
    if profile:
        wanted = {
            component.ref for component in ProfileStore(workspace).get(profile).spec.components
        }
        records = [record for record in records if record.asset_id in wanted]
    else:
        records = [record for record in records if record.kind is CapabilityType.SKILL]

    # ---------------------------------------------------------------- 冲突
    conflicts: list[dict[str, str]] = []
    blocked: dict[str, list[str]] = {name: [] for name in names}
    for name in names:
        for item in store.find_conflicts(name):
            decision = resolutions.find(item["asset"], item["target"])
            resolved = decision is not None and decision.decision == WORKSPACE
            conflicts.append({**item, "resolution": decision.decision if decision else ""})
            if not resolved:
                blocked[name].append(item["asset"])

    # ---------------------------------------------------------------- 归属
    registry = OwnershipRegistry(workspace.ownership_file)
    unowned: list[dict[str, str]] = []
    for name in names:
        for record in records:
            if record.asset_id in blocked[name]:
                continue
            path = make_adapter(name).skill_path(record.name)
            if not path.exists():
                continue
            try:
                registry.check(path)
            except Conflict as exc:
                unowned.append(
                    {
                        "target": name,
                        "asset": record.asset_id,
                        "path": str(path),
                        "reason": exc.details.get("reason", "not_owned"),
                    }
                )
                blocked[name].append(record.asset_id)

    # ---------------------------------------------------------------- 计划
    plans = []
    for name in names:
        assets = [record.asset_id for record in records if record.asset_id not in blocked[name]]
        if not assets:
            continue
        plans.extend(build_plans_for(workspace, make_profile("sync", assets, [name]), [name]))

    # ---------------------------------------------------------------- 同步
    from capnest.commands.apply import deploy

    result = deploy(workspace, plans, yes=yes, dry_run=dry_run)

    # ---------------------------------------------------------------- 校验
    verified: list[dict[str, str]] = []
    for name in names:
        for record in records:
            if record.asset_id in blocked[name]:
                continue
            path = make_adapter(name).skill_path(record.name)
            if not path.is_dir():
                verified.append({"target": name, "asset": record.asset_id, "state": "missing"})
                continue
            same = content_hash(path) == content_hash(record.path)
            verified.append(
                {
                    "target": name,
                    "asset": record.asset_id,
                    "state": "in-sync" if same else "differs",
                }
            )

    payload = {
        "targets": names,
        "adoption": adoption,
        "assets": [record.asset_id for record in records],
        "duplicates": store.find_duplicates(),
        "conflicts": conflicts,
        "blocked": {name: items for name, items in blocked.items() if items},
        "unowned": unowned,
        "deploy": result,
        "verified": verified,
    }
    human = _render(payload)
    unresolved = [item for item in conflicts if item.get("resolution") != WORKSPACE]
    if unresolved:
        raise Conflict(
            f"有 {len(unresolved)} 处冲突未裁决，这些目标上没有同步",
            {
                "conflicts": unresolved,
                "blocked": payload["blocked"],
                "deploy": result,
                "verified": verified,
            },
        )
    context.output.success(payload, human=human)


def _render(payload: dict) -> str:
    """人类可读摘要。"""
    lines: list[str] = []
    adoption = payload.get("adoption") or {}
    if adoption:
        lines.append(
            f"收编 {len(adoption.get('adopted', []))} 个 skill"
            f"（去重 {len(adoption.get('duplicates', []))}，"
            f"冲突 {len(adoption.get('conflicts', []))}，"
            f"跳过 {len(adoption.get('skipped', []))}）"
        )
    lines.append(f"待同步资产 {len(payload['assets'])} 个 → 目标 {', '.join(payload['targets'])}")
    for group in payload["duplicates"]:
        lines.append(f"  = 重复内容：{'  =  '.join(group['names'])}")
    for item in payload["conflicts"]:
        mark = item.get("resolution") or "未裁决"
        lines.append(f"  ! 冲突 {item['asset']} @ {item['target']}（{mark}）")
    for name, items in payload["blocked"].items():
        lines.append(f"  × {name} 未同步：{', '.join(items)}")
    for item in payload["unowned"]:
        lines.append(f"  × 无法证明归属：{item['target']}/{item['asset']}")
    deploy_result = payload["deploy"]
    if deploy_result.get("dry_run"):
        lines.append(f"预演：将写入 {len(deploy_result.get('would_write', []))} 个 skill")
    else:
        lines.append(f"已同步 {len(deploy_result.get('applied', []))} 个目标")
    in_sync = sum(1 for item in payload["verified"] if item["state"] == "in-sync")
    differs = sum(1 for item in payload["verified"] if item["state"] == "differs")
    lines.append(f"校验：一致 {in_sync}，不一致 {differs}")
    return "\n".join(lines)
