"""隐藏 Unicode 扫描：四类字符各至少一条。"""

from __future__ import annotations

from pathlib import Path

from capnest.security.scan import categorize, scan_file, scan_text, scan_tree


def test_zero_width_is_detected() -> None:
    findings = scan_text("hello\u200bworld")
    assert findings
    assert findings[0].category == "zero-width"
    assert findings[0].line == 1


def test_bidi_is_detected() -> None:
    findings = scan_text("safe\u202eevil")
    assert findings
    assert findings[0].category == "bidi"


def test_tag_character_is_detected() -> None:
    findings = scan_text("safe\U000e0041evil")
    assert findings
    assert findings[0].category == "tag"


def test_homoglyph_is_detected() -> None:
    findings = scan_text("\u0440\u0430\u0443\u043f\u0430\u043b")  # 西里尔 р/а/у
    assert findings
    assert {item.category for item in findings} == {"homoglyph"}


def test_fullwidth_latin_is_detected() -> None:
    findings = scan_text("\uff21\uff22\uff23")
    assert findings
    assert findings[0].category == "homoglyph"


def test_plain_text_is_clean() -> None:
    assert scan_text("这是一段普通的中文 English 文本 123。") == []


def test_categorize_ignores_ordinary_characters() -> None:
    assert categorize("a") is None
    assert categorize("中") is None


def test_scan_file_skips_binary(tmp_path: Path) -> None:
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\x00\x01hello")
    assert scan_file(path) == []


def test_scan_tree_reports_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "SKILL.md").write_text("x\u200ey", encoding="utf-8")
    findings = scan_tree(tmp_path)
    assert findings
    assert findings[0].file == "nested/SKILL.md"


def test_line_and_column_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text("first\nsecond\u200e\n", encoding="utf-8")
    findings = scan_file(path)
    assert findings[0].line == 2
    assert findings[0].column == 7
