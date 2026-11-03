"""M1 命令的端到端行为：退出码与 JSON 契约。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path, run_cli) -> Path:
    path = tmp_path / "ws"
    initialized = run_cli("init", str(path))
    assert initialized.returncode == 0, initialized.stderr
    return path


def make_skill(directory: Path, name: str = "demo") -> Path:
    root = directory / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\nname: demo\ndescription: 演示用的 skill\n---\n\n正文\n",
        encoding="utf-8",
    )
    return root


def test_add_then_list(run_cli, tmp_path: Path, workspace: Path) -> None:
    source = make_skill(tmp_path)
    added = run_cli("--json", "add", "skill", str(source), workspace=workspace)
    assert added.returncode == 0, added.stderr
    assert added.data["id"] == "skills/demo"

    listed = run_cli("--json", "list", workspace=workspace)
    assert listed.returncode == 0
    assert listed.data["count"] == 1
    assert listed.data["assets"][0]["id"] == "skills/demo"


def test_add_duplicate_exits_7(run_cli, tmp_path: Path, workspace: Path) -> None:
    source = make_skill(tmp_path)
    run_cli("add", "skill", str(source), workspace=workspace)
    again = run_cli("--json", "add", "skill", str(source), workspace=workspace)
    assert again.returncode == 7
    assert again.json["error"]["code"] == "CONFLICT"


def test_add_without_arguments_exits_2(run_cli, workspace: Path) -> None:
    result = run_cli("--json", "add", workspace=workspace)
    assert result.returncode == 2


def test_add_unsafe_content_exits_6(run_cli, tmp_path: Path, workspace: Path) -> None:
    source = make_skill(tmp_path)
    (source / "SKILL.md").write_text("x\u200ey", encoding="utf-8")
    result = run_cli("--json", "add", "skill", str(source), workspace=workspace)
    assert result.returncode == 6
    assert result.json["error"]["code"] == "UNSAFE_CONTENT"
    assert result.json["error"]["details"]["findings"]


def test_commands_require_an_initialized_workspace(run_cli, tmp_path: Path) -> None:
    result = run_cli("--json", "list", workspace=tmp_path / "nowhere")
    assert result.returncode == 8
    assert result.json["error"]["code"] == "NOT_FOUND"


def test_search_matches_name(run_cli, tmp_path: Path, workspace: Path) -> None:
    source = make_skill(tmp_path)
    run_cli("add", "skill", str(source), workspace=workspace)
    hit = run_cli("--json", "search", "demo", workspace=workspace)
    assert hit.returncode == 0
    assert hit.data["count"] == 1
    miss = run_cli("--json", "search", "不存在的关键词", workspace=workspace)
    assert miss.returncode == 0
    assert miss.data["count"] == 0


def test_validate_exits_0_when_clean(run_cli, tmp_path: Path, workspace: Path) -> None:
    source = make_skill(tmp_path)
    run_cli("add", "skill", str(source), workspace=workspace)
    result = run_cli("--json", "validate", workspace=workspace)
    assert result.returncode == 0
    assert result.data["error_count"] == 0


def test_validate_exits_3_on_error(run_cli, tmp_path: Path, workspace: Path) -> None:
    source = make_skill(tmp_path)
    run_cli("add", "skill", str(source), workspace=workspace)
    manifest = workspace / "assets" / "skills" / "demo" / "capability.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("id: skills/demo", "id: skills/other"),
        encoding="utf-8",
    )
    result = run_cli("--json", "validate", workspace=workspace)
    assert result.returncode == 3
    assert result.json["error"]["code"] == "VALIDATION_FAILED"
    assert result.json["error"]["details"]["violations"]


def test_profile_create_list_show(run_cli, tmp_path: Path, workspace: Path) -> None:
    source = make_skill(tmp_path)
    run_cli("add", "skill", str(source), workspace=workspace)

    created = run_cli(
        "--json",
        "profile",
        "create",
        "data-agent",
        "--asset",
        "skills/demo",
        "--target",
        "mcode",
        workspace=workspace,
    )
    assert created.returncode == 0
    assert created.data["components"] == ["skills/demo"]

    listed = run_cli("--json", "profile", "list", workspace=workspace)
    assert listed.data["count"] == 1

    shown = run_cli("--json", "profile", "show", "data-agent", workspace=workspace)
    assert shown.returncode == 0
    assert shown.data["components"][0]["resolved"] is True


def test_profile_create_duplicate_exits_7(run_cli, tmp_path: Path, workspace: Path) -> None:
    run_cli("profile", "create", "data-agent", workspace=workspace)
    again = run_cli("--json", "profile", "create", "data-agent", workspace=workspace)
    assert again.returncode == 7


def test_profile_create_with_unknown_asset_exits_8(run_cli, workspace: Path) -> None:
    result = run_cli(
        "--json",
        "profile",
        "create",
        "data-agent",
        "--asset",
        "skills/nope",
        workspace=workspace,
    )
    assert result.returncode == 8


def test_profile_show_missing_exits_8(run_cli, workspace: Path) -> None:
    result = run_cli("--json", "profile", "show", "nope", workspace=workspace)
    assert result.returncode == 8
