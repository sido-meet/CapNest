"""工作区解析与目标目录定位。"""

from __future__ import annotations

from pathlib import Path

from capnest.config import (
    WorkspaceConfig,
    default_target_paths,
    find_config_file,
    load_config,
    resolve_workspace,
    save_config,
)


def test_explicit_workspace_wins(tmp_path: Path):
    assert resolve_workspace(tmp_path / "ws", env={}, cwd=tmp_path) == (tmp_path / "ws").resolve()


def test_env_var_comes_before_config_file(tmp_path: Path):
    (tmp_path / "config.yaml").write_text("version: 1\nworkspace: .\n", encoding="utf-8")
    env_home = tmp_path / "from-env"
    resolved = resolve_workspace(None, env={"CAPNEST_HOME": str(env_home)}, cwd=tmp_path)
    assert resolved == env_home.resolve()


def test_config_file_workspace_is_relative_to_its_own_directory(tmp_path: Path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "config.yaml").write_text("version: 1\nworkspace: ..\n", encoding="utf-8")
    resolved = resolve_workspace(None, env={}, cwd=nested)
    assert resolved == tmp_path.resolve()


def test_fallback_is_current_directory(tmp_path: Path):
    assert resolve_workspace(None, env={}, cwd=tmp_path) == tmp_path.resolve()


def test_find_config_file_walks_up(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n", encoding="utf-8")
    assert find_config_file(nested) == config.resolve()


def test_target_paths_use_home_by_default(tmp_path: Path):
    paths = default_target_paths("mcode", env={}, home=tmp_path)
    assert paths.home == tmp_path / ".minimax"
    assert paths.config_file == tmp_path / ".minimax" / "config.yaml"
    assert paths.skills_path == tmp_path / ".minimax" / "skills"


def test_claude_code_config_lives_next_to_dot_claude(tmp_path: Path):
    paths = default_target_paths("claude-code", env={}, home=tmp_path)
    assert paths.home == tmp_path / ".claude"
    assert paths.config_file == tmp_path / ".claude.json"
    assert paths.skills_path == tmp_path / ".claude" / "skills"


def test_target_home_override(tmp_path: Path):
    override = tmp_path / "elsewhere"
    paths = default_target_paths("mcode", env={"CAPNEST_TARGET_HOME_MCODE": str(override)})
    assert paths.home == override
    assert paths.skills_path == override / "skills"


def test_config_round_trip(tmp_path: Path):
    config = WorkspaceConfig(default_profile="data-agent", default_targets=["mcode"])
    path = tmp_path / "config.yaml"
    save_config(path, config)
    loaded = load_config(path)
    assert loaded.default_profile == "data-agent"
    assert loaded.default_targets == ["mcode"]
    assert loaded.deployment_mode == "copy"
