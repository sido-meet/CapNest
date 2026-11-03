"""Adapter：读取、归一化、能力矩阵。"""

from __future__ import annotations

from pathlib import Path

from capnest.adapters import make_adapter
from capnest.adapters.claude_code import ClaudeCodeAdapter
from capnest.adapters.mcode import McodeAdapter
from capnest.models import CapabilityType, DeploymentMode


def make_home(root: Path, name: str, nested: bool = False) -> Path:
    """造一个目标 skills 目录。"""
    skills = root / "skills"
    skill = skills / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: x\n---\n\n正文\n", encoding="utf-8")
    if nested:
        (skill / "sub").mkdir()
        (skill / "sub" / "SKILL.md").write_text("---\nname: sub\n---\n", encoding="utf-8")
    return skills


def test_mcode_reads_skills(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "mcode"
    make_home(home, "alpha")
    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(home))

    adapter = make_adapter("mcode")
    state = adapter.read()
    assert "alpha" in state.skills
    assert state.skills["alpha"].startswith("sha256:")


def test_claude_code_reads_skills(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "claude"
    make_home(home, "beta")
    monkeypatch.setenv("CAPNEST_TARGET_HOME_CLAUDE_CODE", str(home))

    adapter = make_adapter("claude-code")
    state = adapter.read()
    assert "beta" in state.skills


def test_nested_skills_are_reported(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "mcode"
    make_home(home, "alpha", nested=True)
    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(home))

    state = make_adapter("mcode").read()
    assert state.nested == ("alpha",)


def test_hidden_directories_are_not_skills(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "mcode"
    skills = make_home(home, "alpha")
    (skills / ".capnest-stage-xyz").mkdir()
    (skills / ".capnest-stage-xyz" / "SKILL.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(home))

    state = make_adapter("mcode").read()
    assert list(state.skills) == ["alpha"]


def test_builtin_skills_are_never_read(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "mcode"
    builtin = home / ".builtin-skills" / "internal"
    builtin.mkdir(parents=True)
    (builtin / "SKILL.md").write_text("内置\n", encoding="utf-8")
    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(home))

    state = make_adapter("mcode").read()
    assert state.skills == {}


def test_capabilities_declare_the_first_knife_boundary(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "mcode"
    home.mkdir()
    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(home))

    capabilities = make_adapter("mcode").capabilities()
    assert capabilities.target == "mcode"
    assert capabilities.supports == frozenset({CapabilityType.SKILL})
    assert capabilities.deployment_modes == frozenset({DeploymentMode.COPY})
    assert capabilities.mcp_backend is None
    assert capabilities.skills_path == home / "skills"


def test_claude_code_config_lives_above_the_home(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(tmp_path / ".claude")
    assert adapter.config_file == tmp_path / ".claude.json"


def test_mcode_config_lives_inside_the_home(tmp_path: Path) -> None:
    adapter = McodeAdapter(tmp_path / ".minimax")
    assert adapter.config_file == tmp_path / ".minimax" / "config.yaml"


def test_unknown_target_is_not_found() -> None:
    from capnest.errors import NotFound

    try:
        make_adapter("codex")
    except NotFound as exc:
        assert exc.exit_code == 8
    else:  # pragma: no cover
        raise AssertionError("应当抛出 NotFound")


def test_golden_fixture_is_readable(tmp_path: Path, monkeypatch) -> None:
    """实测样本：mcode 配置 + 合成 skill 样本能被 Adapter 读出来。"""
    fixtures = Path(__file__).parent / "fixtures"
    home = tmp_path / "mcode"
    skill = home / "skills" / "capnest-sample"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        (fixtures / "skill" / "SKILL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (home / "config.yaml").write_text(
        (fixtures / "mcode_config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setenv("CAPNEST_TARGET_HOME_MCODE", str(home))

    state = make_adapter("mcode").read()
    assert "capnest-sample" in state.skills
    assert state.config_fingerprint.startswith("sha256:")
