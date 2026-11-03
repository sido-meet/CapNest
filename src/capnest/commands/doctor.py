"""`capnest doctor`：自检，不改任何东西。

检查项分三类：运行环境、工作区、目标 Agent。
有 `fail` 的检查项时退出码为 1，只有 `warn` 时仍为 0。
"""

from __future__ import annotations

import shutil
import sys
from typing import Any

import typer

from capnest.config import default_target_paths_all
from capnest.context import AppContext, use_json, workspace_of
from capnest.store.workspace import Workspace

#: 各目标 Agent 的 CLI 与版本参数。
_AGENT_CLIS: dict[str, tuple[str, ...]] = {
    "mcode": ("mcode", "--version"),
    "claude-code": ("claude", "--version"),
}


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _check_python() -> dict[str, str]:
    version = ".".join(str(part) for part in sys.version_info[:3])
    return _check("python_version", "ok", version)


def _check_workspace(workspace: Workspace) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    if not workspace.root.is_dir():
        checks.append(_check("workspace", "fail", f"{workspace.root} 不存在"))
        return checks
    checks.append(_check("workspace", "ok", str(workspace.root)))
    if not workspace.is_initialized():
        checks.append(_check("workspace.config", "fail", "缺少 config.yaml，请先运行 capnest init"))
        return checks
    checks.append(_check("workspace.config", "ok", str(workspace.config_file)))
    missing = [
        name
        for name, path in (
            ("assets", workspace.assets_dir),
            ("profiles", workspace.profiles_dir),
            ("state", workspace.state_dir),
        )
        if not path.is_dir()
    ]
    if missing:
        checks.append(_check("workspace.layout", "warn", f"缺少目录：{', '.join(missing)}"))
    else:
        checks.append(_check("workspace.layout", "ok", "assets / profiles / state 齐备"))
    return checks


def _check_targets(workspace: Workspace, targets: list[str]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    paths = default_target_paths_all()
    for name in targets:
        target_paths = paths.get(name)
        if target_paths is None:
            checks.append(_check(f"target.{name}", "fail", "未知的目标"))
            continue
        home = target_paths.home
        if home.is_dir():
            checks.append(_check(f"target.{name}.home", "ok", str(home)))
        else:
            checks.append(_check(f"target.{name}.home", "warn", f"{home} 不存在"))
        config_file = target_paths.config_file
        if config_file.is_file():
            checks.append(_check(f"target.{name}.config", "ok", str(config_file)))
        else:
            checks.append(_check(f"target.{name}.config", "warn", f"{config_file} 不存在"))
        binary = shutil.which(_AGENT_CLIS[name][0]) if name in _AGENT_CLIS else None
        if binary:
            checks.append(_check(f"target.{name}.cli", "ok", binary))
        else:
            checks.append(_check(f"target.{name}.cli", "warn", f"{name} 的 CLI 不在 PATH 上"))
    return checks


def _capabilities() -> dict[str, Any]:
    """Adapter 能力矩阵（M2 起补全形态与后端信息）。"""
    paths = default_target_paths_all()
    return {
        name: {
            "supports": ["skill"],
            "deployment_modes": ["copy"],
            "skills_path": str(target.skills_path),
            "mcp_backend": None,
        }
        for name, target in paths.items()
    }


def doctor(
    ctx: typer.Context,
    target: list[str] = typer.Option([], "--target", help="只检查指定目标"),
    json_: bool = typer.Option(False, "--json", help="以 JSON 输出到 stdout"),
) -> None:
    """自检：运行环境、工作区与目标 Agent。"""
    context: AppContext = ctx.obj
    context.output.command = "doctor"
    use_json(context, json_)

    all_targets = sorted(default_target_paths_all())
    selected = [name for name in target if name in all_targets] if target else all_targets

    workspace = workspace_of(context)

    checks: list[dict[str, str]] = [_check_python()]
    checks.extend(_check_workspace(workspace))
    checks.extend(_check_targets(workspace, selected))

    failed = [c for c in checks if c["status"] == "fail"]
    payload = {
        "checks": checks,
        "capabilities": _capabilities(),
        "workspace": str(workspace.root),
    }
    human = "\n".join(f"{c['status']:>4}  {c['name']:<28} {c['detail']}" for c in checks)
    context.output.success(payload, human=human)
    if failed:
        raise typer.Exit(1)
