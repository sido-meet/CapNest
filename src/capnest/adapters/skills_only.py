"""只读写 skills 目录的 Adapter 基类。

两个目标在第一刀里的差别只有「skills 目录在哪、配置文件在哪」，
所以差异全部收敛到子类里，行为写在基类。
"""

from __future__ import annotations

from pathlib import Path

from capnest.adapters.base import TargetCapabilities, TargetState
from capnest.hashing import hash_dir, hash_file


class SkillsOnlyAdapter:
    """skills 目录的只读与定位。"""

    target: str = ""

    def __init__(self, skills_path: Path, config_file: Path | None = None) -> None:
        self.skills_path = skills_path
        self.config_file = config_file

    # ------------------------------------------------------------------ 能力

    def capabilities(self) -> TargetCapabilities:
        return TargetCapabilities(
            target=self.target,
            skills_path=self.skills_path,
            config_file=self.config_file,
            mcp_backend=None,
            notes="第一刀只读写 skills 目录；MCP 段在第二刀加入",
        )

    # ------------------------------------------------------------------ 读

    def read(self) -> TargetState:
        """读出目标侧现状。**只读**，一个字节都不写。"""
        skills: dict[str, str] = {}
        nested: list[str] = []
        if self.skills_path.is_dir():
            for item in sorted(self.skills_path.iterdir()):
                if not item.is_dir():
                    continue
                if item.name.startswith("."):
                    # 隐藏目录（`.builtin-skills`、暂存目录等）不是 skill。
                    continue
                skills[item.name] = hash_dir(item)
                if self._contains_nested_skill(item):
                    nested.append(item.name)
        return TargetState(
            skills=skills,
            nested=tuple(nested),
            config_fingerprint=self._config_fingerprint(),
        )

    @staticmethod
    def _contains_nested_skill(directory: Path) -> bool:
        """目录里是否**套着**另一个 skill。

        判据是「子目录里还有 `SKILL.md`」——像 `ai-research-skills/0-autoresearch-skill/SKILL.md`
        这种。普通的资源目录（`references/`、`scripts/`）不算。
        """
        return any(manifest.parent != directory for manifest in directory.rglob("SKILL.md"))

    def _config_fingerprint(self) -> str:
        """配置文件的指纹。第一刀只读不写，但它被并发修改的风险最高。"""
        if self.config_file is None or not self.config_file.is_file():
            return ""
        return hash_file(self.config_file)

    # ------------------------------------------------------------------ 定位

    def skill_path(self, name: str) -> Path:
        """目标侧某个 skill 的落点。"""
        return self.skills_path / name
