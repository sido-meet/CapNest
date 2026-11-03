"""`capnest init`：创建工作区骨架。

工作区是 CapNest 的根目录：资产、Profile 与状态都在这里。
"""

from __future__ import annotations

from pathlib import Path

import typer

from capnest.config import (
    WorkspaceConfig,
    default_target_paths_all,
    load_config,
    save_config,
)
from capnest.context import AppContext
from capnest.errors import Conflict
from capnest.store.workspace import Workspace


def init(
    ctx: typer.Context,
    path: Path = typer.Argument(Path("."), help="工作区根目录"),
    force: bool = typer.Option(False, "--force", help="已初始化时仍然覆盖配置"),
) -> None:
    """创建工作区骨架与 `config.yaml`。"""
    context: AppContext = ctx.obj
    context.output.command = "init"

    root = path.expanduser().resolve()
    workspace = Workspace(root)
    context.workspace = root

    if workspace.is_initialized() and not force:
        raise Conflict(
            "工作区已初始化，如需覆盖请加 --force",
            {"workspace": str(root)},
        )

    workspace.ensure_layout()
    if not workspace.deployments_file.exists():
        workspace.deployments_file.write_text("[]\n", encoding="utf-8")
    if not workspace.ownership_file.exists():
        workspace.ownership_file.write_text("{}\n", encoding="utf-8")

    config = load_config(workspace.config_file) if workspace.is_initialized() else WorkspaceConfig()
    config.workspace = "."
    paths = default_target_paths_all()
    for name, target_paths in paths.items():
        existing = config.targets.get(name, {})
        config.targets[name] = {
            "home": existing.get("home", str(target_paths.home)),
            "config_file": existing.get("config_file", str(target_paths.config_file)),
        }
    save_config(workspace.config_file, config)

    created = sorted(
        str(p.relative_to(root)).replace("\\", "/")
        for p in (
            workspace.assets_dir,
            workspace.profiles_dir,
            workspace.state_dir,
            workspace.config_file,
        )
    )
    context.output.success(
        {"workspace": str(root), "created": created},
        human=f"已初始化工作区：{root}",
    )
