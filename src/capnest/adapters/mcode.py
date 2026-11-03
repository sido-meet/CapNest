"""mcode（MiniMax Code）Adapter。

落点：`~/.minimax/skills/<name>/`；用户配置 `~/.minimax/config.yaml`。

**绝不触碰 `~/.minimax/.builtin-skills/`**——那是内置 skill 目录。
"""

from __future__ import annotations

from pathlib import Path

from capnest.adapters.skills_only import SkillsOnlyAdapter

#: 内置 skill 目录名。任何情况下都不读写它。
BUILTIN_SKILLS_DIR = ".builtin-skills"


class McodeAdapter(SkillsOnlyAdapter):
    """mcode 目标。"""

    target = "mcode"

    def __init__(self, home: Path, config_file: Path | None = None) -> None:
        super().__init__(home / "skills", config_file or home / "config.yaml")
        self.home = home

    @property
    def builtin_skills_path(self) -> Path:
        """内置 skill 目录——只用于确认它存在，不读不写。"""
        return self.home / BUILTIN_SKILLS_DIR
