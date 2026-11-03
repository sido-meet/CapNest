"""工作区的目录布局。

文件是唯一事实来源：`init` 建出来的骨架就是全部需要的东西。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ASSET_DIRS: tuple[str, ...] = ("mcp", "skills", "workflows")


@dataclass(frozen=True)
class Workspace:
    """工作区根目录及其下的固定路径。"""

    root: Path

    @property
    def config_file(self) -> Path:
        return self.root / "config.yaml"

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def skills_dir(self) -> Path:
        return self.assets_dir / "skills"

    @property
    def mcp_dir(self) -> Path:
        return self.assets_dir / "mcp"

    @property
    def workflows_dir(self) -> Path:
        return self.assets_dir / "workflows"

    @property
    def profiles_dir(self) -> Path:
        return self.root / "profiles"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def deployments_file(self) -> Path:
        return self.state_dir / "deployments.json"

    @property
    def ownership_file(self) -> Path:
        return self.state_dir / "ownership.json"

    @property
    def backups_dir(self) -> Path:
        return self.state_dir / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.state_dir / "logs"

    def asset_dir(self, kind: str) -> Path:
        """按资产类型给出 `assets/` 下的目录。"""
        return self.assets_dir / kind

    def ensure_layout(self) -> None:
        """创建骨架。已存在的目录不动。"""
        for name in ASSET_DIRS:
            (self.assets_dir / name).mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def is_initialized(self) -> bool:
        return self.config_file.is_file()
