"""删除工作区里的一个文件 → 两边都删掉。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path, run_cli) -> Path:
    path = tmp_path / "ws"
    assert run_cli("init", str(path)).returncode == 0
    return path


def test_deleting_a_file_propagates_to_both_targets(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    skill = target_homes["claude-code"] / "skills" / "docx"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: docx\n---\n\n正文\n", encoding="utf-8")
    (skill / "extra.md").write_text("多出来的\n", encoding="utf-8")

    assert (
        run_cli("add", "--from", "claude-code:*", workspace=workspace, env=sandbox_env).returncode
        == 0
    )
    first = run_cli("--json", "sync", "--yes", workspace=workspace, env=sandbox_env)
    assert first.returncode == 0, first.stdout

    # 工作区里删掉那个文件
    (workspace / "assets" / "skills" / "docx" / "extra.md").unlink()

    result = run_cli("--json", "sync", "--yes", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stdout
    for home in target_homes.values():
        assert not (home / "skills" / "docx" / "extra.md").exists()
        assert (home / "skills" / "docx" / "SKILL.md").is_file()
