"""工作区配置与目标目录定位。

工作区解析顺序（第一个命中的生效）：

1. `--workspace PATH`
2. 环境变量 `CAPNEST_HOME`
3. 从当前目录向上逐级查找最近的 `config.yaml`，取其 `workspace` 字段
   （相对该文件所在目录解析）
4. 当前目录

目标目录定位：`CAPNEST_TARGET_HOME_<TARGET>` 覆盖某个 target 的 home（沙箱与测试用），
否则用用户主目录下的已知路径。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from capnest.errors import NotFound

#: 首期支持的两个部署目标。
DEFAULT_TARGETS: tuple[str, ...] = ("mcode", "claude-code")

#: 目标 home 在用户主目录下的相对位置。
_TARGET_HOME_RELATIVE: dict[str, str] = {
    "mcode": ".minimax",
    "claude-code": ".claude",
}

CONFIG_FILENAME = "config.yaml"


@dataclass(frozen=True)
class TargetPaths:
    """一个部署目标在磁盘上的位置。"""

    target: str
    home: Path
    config_file: Path
    skills_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "target": self.target,
            "home": str(self.home),
            "config_file": str(self.config_file),
            "skills_path": str(self.skills_path),
        }


@dataclass
class WorkspaceConfig:
    """`config.yaml` 的内存表示。"""

    version: int = 1
    workspace: str = "."
    default_profile: str | None = None
    default_targets: list[str] = field(default_factory=lambda: list(DEFAULT_TARGETS))
    deployment_mode: str = "copy"
    targets: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "workspace": self.workspace,
            "default_profile": self.default_profile,
            "default_targets": list(self.default_targets),
            "deployment": {"mode": self.deployment_mode},
            "targets": {name: dict(paths) for name, paths in self.targets.items()},
        }


def _env_var_for_target(target: str) -> str:
    return "CAPNEST_TARGET_HOME_" + target.upper().replace("-", "_")


def target_home_override(target: str, env: Mapping[str, str] | None = None) -> Path | None:
    """返回该 target 的 home 覆盖值，没有则返回 None。"""
    environ = os.environ if env is None else env
    raw = environ.get(_env_var_for_target(target))
    return Path(raw).expanduser() if raw else None


def default_target_paths(
    target: str,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> TargetPaths:
    """定位一个目标的 home、配置文件与 skills 目录。"""
    base = home if home is not None else Path.home()
    override = target_home_override(target, env)
    target_home = (
        override if override is not None else base / _TARGET_HOME_RELATIVE.get(target, f".{target}")
    )
    return TargetPaths(
        target=target,
        home=target_home,
        config_file=_config_file_for(target, target_home, overridden=override is not None),
        skills_path=target_home / "skills",
    )


def _config_file_for(target: str, home: Path, *, overridden: bool) -> Path:
    """目标的配置文件位置。

    mcode 的配置在数据目录里（`~/.minimax/config.yaml`）；
    Claude Code 的用户级配置在**主目录**下（`~/.claude.json`），不在 `.claude/` 里。
    home 被环境变量覆盖时，配置文件一律落在覆盖目录内，便于沙箱自洽。
    """
    if target == "claude-code":
        return home / ".claude.json" if overridden else home.parent / ".claude.json"
    return home / "config.yaml"


def default_target_paths_all(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, TargetPaths]:
    return {name: default_target_paths(name, env, home) for name in DEFAULT_TARGETS}


def find_config_file(start: Path) -> Path | None:
    """从 `start` 向上逐级查找最近的 `config.yaml`。"""
    try:
        current = start.resolve()
    except OSError:  # pragma: no cover - 极端情况下 resolve 失败
        return None
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def resolve_workspace(
    explicit: Path | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    """按既定优先级解析工作区根目录。"""
    environ = os.environ if env is None else env
    here = cwd if cwd is not None else Path.cwd()

    if explicit is not None:
        return explicit.expanduser().resolve()
    raw_env = environ.get("CAPNEST_HOME")
    if raw_env:
        return Path(raw_env).expanduser().resolve()

    config_file = find_config_file(here)
    if config_file is not None:
        config = load_config(config_file)
        workspace = (config_file.parent / config.workspace).resolve()
        return workspace
    return here.resolve()


def load_config(path: Path) -> WorkspaceConfig:
    """读取 `config.yaml`；文件不存在时返回默认配置。"""
    if not path.is_file():
        return WorkspaceConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return WorkspaceConfig()
    targets = raw.get("targets") or {}
    deployment = raw.get("deployment") or {}
    return WorkspaceConfig(
        version=int(raw.get("version", 1)),
        workspace=str(raw.get("workspace", ".")),
        default_profile=raw.get("default_profile"),
        default_targets=list(raw.get("default_targets") or DEFAULT_TARGETS),
        deployment_mode=str(deployment.get("mode", "copy")),
        targets={str(k): dict(v) for k, v in targets.items() if isinstance(v, dict)},
    )


def save_config(path: Path, config: WorkspaceConfig) -> None:
    """写出 `config.yaml`。"""
    text = yaml.safe_dump(
        config.to_dict(),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def require_initialized(workspace: Path) -> WorkspaceConfig:
    """工作区必须已初始化，否则报 NOT_FOUND。"""
    config_file = workspace / CONFIG_FILENAME
    if not config_file.is_file():
        raise NotFound(
            "工作区尚未初始化，请先运行 `capnest init`",
            {"workspace": str(workspace)},
        )
    return load_config(config_file)
