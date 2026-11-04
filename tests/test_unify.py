"""统一管理：收编 → 去重 → 冲突 → 同步。

这些测试全部在临时目录里跑，不碰用户真实的 Agent 目录。
"""

from __future__ import annotations

from pathlib import Path

import pytest


def make_skill(home: Path, name: str, *, body: str = "正文\n", frontmatter: bool = True) -> Path:
    directory = home / "skills" / name
    directory.mkdir(parents=True, exist_ok=True)
    header = f"---\nname: {name}\n---\n\n" if frontmatter else ""
    (directory / "SKILL.md").write_text(f"{header}{body}", encoding="utf-8")
    return directory


@pytest.fixture
def workspace(tmp_path: Path, run_cli) -> Path:
    path = tmp_path / "ws"
    assert run_cli("init", str(path)).returncode == 0
    return path


def test_adopt_all_targets_collects_both_sides(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    make_skill(target_homes["mcode"], "manim")
    make_skill(target_homes["claude-code"], "docx")

    result = run_cli("--json", "add", "--from", "*", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stderr
    assert {item["id"] for item in result.data["adopted"]} == {"skills/manim", "skills/docx"}


def test_same_content_is_deduplicated(run_cli, workspace, target_homes, sandbox_env) -> None:
    """两个 Agent 侧有同一份内容 → 只留一份，来源合并。"""
    make_skill(target_homes["mcode"], "shared")
    make_skill(target_homes["claude-code"], "shared")

    result = run_cli("--json", "add", "--from", "*", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stderr
    assert len(result.data["adopted"]) == 1
    assert len(result.data["duplicates"]) == 1

    listed = run_cli("--json", "list", workspace=workspace, env=sandbox_env)
    assert listed.data["count"] == 1
    sources = listed.data["assets"][0]["sources"]
    assert {item["target"] for item in sources} == {"mcode", "claude-code"}


def test_same_name_different_content_is_a_conflict(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    make_skill(target_homes["claude-code"], "docx", body="claude 版\n")
    make_skill(target_homes["mcode"], "docx", body="mcode 版\n")

    result = run_cli("--json", "add", "--from", "*", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stderr
    assert len(result.data["conflicts"]) == 1
    # 工作区里保留先收进来的那一份，没有被覆盖。
    listed = run_cli("--json", "list", workspace=workspace, env=sandbox_env)
    assert listed.data["count"] == 1


def test_adopted_target_can_be_updated_by_apply(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    """收编之后 CapNest 就管这份能力：改工作区 → apply 能覆盖目标。"""
    home = target_homes["claude-code"]
    make_skill(home, "docx")
    run_cli("add", "--from", "claude-code:*", workspace=workspace, env=sandbox_env)

    skill_md = workspace / "assets" / "skills" / "docx" / "SKILL.md"
    skill_md.write_text("---\nname: docx\n---\n\n改过的正文\n", encoding="utf-8")

    applied = run_cli(
        "--json",
        "apply",
        "--profile",
        "none",
        workspace=workspace,
        env=sandbox_env,
    )
    # 没有这个 Profile → 报错，但**不能**是归属错误。
    assert applied.returncode != 0
    assert "PROFILE" not in applied.stderr.upper()

    created = run_cli(
        "profile", "create", "all", "--asset", "skills/docx", workspace=workspace, env=sandbox_env
    )
    assert created.returncode == 0

    result = run_cli(
        "--json", "apply", "--profile", "all", "--yes", workspace=workspace, env=sandbox_env
    )
    assert result.returncode == 0, result.stderr
    assert (
        (home / "skills" / "docx" / "SKILL.md").read_text(encoding="utf-8").endswith("改过的正文\n")
    )


def test_conflict_list_and_resolve_with_target(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    make_skill(target_homes["claude-code"], "docx", body="claude 版\n")
    make_skill(target_homes["mcode"], "docx", body="mcode 版\n")
    run_cli("add", "--from", "*", workspace=workspace, env=sandbox_env)

    listed = run_cli("--json", "conflict", "list", workspace=workspace, env=sandbox_env)
    assert listed.returncode == 0, listed.stderr
    assert listed.data["count"] == 1

    resolved = run_cli(
        "--json",
        "conflict",
        "resolve",
        "skills/docx",
        "--use",
        "mcode:docx",
        workspace=workspace,
        env=sandbox_env,
    )
    assert resolved.returncode == 0, resolved.stderr

    body = (workspace / "assets" / "skills" / "docx" / "SKILL.md").read_text(encoding="utf-8")
    assert "mcode 版" in body


def test_conflict_resolve_with_workspace_takes_ownership(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    """收编按目标顺序进行（mcode 在前），所以工作区里留下的是 mcode 那份。"""
    make_skill(target_homes["claude-code"], "docx", body="claude 版\n")
    make_skill(target_homes["mcode"], "docx", body="mcode 版\n")
    run_cli("add", "--from", "*", workspace=workspace, env=sandbox_env)

    resolved = run_cli(
        "--json",
        "conflict",
        "resolve",
        "skills/docx",
        "--use",
        "workspace",
        "--target",
        "claude-code",
        workspace=workspace,
        env=sandbox_env,
    )
    assert resolved.returncode == 0, resolved.stderr

    # 以工作区为准 → claude-code 侧被工作区版本覆盖。
    result = run_cli("--json", "sync", "--yes", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stderr
    body = (target_homes["claude-code"] / "skills" / "docx" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "mcode 版" in body


def test_dedupe_reports_same_content_different_names(
    run_cli, workspace, target_homes, sandbox_env
) -> None:
    make_skill(target_homes["mcode"], "alpha", frontmatter=False)
    make_skill(target_homes["claude-code"], "beta", frontmatter=False)
    run_cli("add", "--from", "*", workspace=workspace, env=sandbox_env)

    result = run_cli("--json", "dedupe", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stderr
    assert result.data["count"] == 1
    assert set(result.data["groups"][0]["names"]) == {"alpha", "beta"}


def test_sync_makes_both_targets_identical(run_cli, workspace, target_homes, sandbox_env) -> None:
    make_skill(target_homes["claude-code"], "docx")
    make_skill(target_homes["mcode"], "manim")

    result = run_cli("--json", "sync", "--adopt", "--yes", workspace=workspace, env=sandbox_env)
    assert result.returncode == 0, result.stderr
    states = {item["state"] for item in result.data["verified"]}
    assert states == {"in-sync"}
    # 两边都有同一份能力。
    for home in target_homes.values():
        assert (home / "skills" / "docx" / "SKILL.md").is_file()
        assert (home / "skills" / "manim" / "SKILL.md").is_file()


def test_sync_refuses_unresolved_conflict(run_cli, workspace, target_homes, sandbox_env) -> None:
    make_skill(target_homes["claude-code"], "docx", body="claude 版\n")
    make_skill(target_homes["mcode"], "docx", body="mcode 版\n")

    result = run_cli("--json", "sync", "--adopt", "--yes", workspace=workspace, env=sandbox_env)
    assert result.returncode == 7, result.stdout
    assert result.json["error"]["code"] == "CONFLICT"
    # 冲突没解决 → mcode 侧一个字都没动。
    body = (target_homes["mcode"] / "skills" / "docx" / "SKILL.md").read_text(encoding="utf-8")
    assert "mcode 版" in body
