"""Claude Code Adapter。

落点：`~/.claude/skills/<name>/`；用户级配置 `~/.claude.json`
（**在 home 的上一级**，不在 `.claude/` 里面）。

第一刀只读配置、不写配置——共享大文件的定点块编辑是第二刀的事。
"""

from __future__ import annotations

from pathlib import Path

from capnest.adapters.skills_only import SkillsOnlyAdapter


class ClaudeCodeAdapter(SkillsOnlyAdapter):
    """Claude Code 目标。"""

    target = "claude-code"

    def __init__(self, home: Path, config_file: Path | None = None) -> None:
        super().__init__(home / "skills", config_file or home.parent / ".claude.json")
        self.home = home
