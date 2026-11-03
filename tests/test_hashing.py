"""规范化哈希：规则表逐条有测试。"""

from __future__ import annotations

from pathlib import Path

from capnest.hashing import hash_dir, hash_file


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_same_content_same_hash(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    _write(first / "SKILL.md", b"hello\n")
    _write(second / "SKILL.md", b"hello\n")
    assert hash_dir(first) == hash_dir(second)


def test_one_byte_change_changes_hash(tmp_path: Path) -> None:
    directory = tmp_path / "a"
    _write(directory / "SKILL.md", b"hello\n")
    before = hash_dir(directory)
    _write(directory / "SKILL.md", b"hello!\n")
    assert hash_dir(directory) != before


def test_crlf_and_lf_hash_the_same(tmp_path: Path) -> None:
    unix = tmp_path / "unix"
    windows = tmp_path / "windows"
    _write(unix / "SKILL.md", b"line1\nline2\n")
    _write(windows / "SKILL.md", b"line1\r\nline2\r\n")
    assert hash_dir(unix) == hash_dir(windows)


def test_cr_only_normalized(tmp_path: Path) -> None:
    unix = tmp_path / "unix"
    mac = tmp_path / "mac"
    _write(unix / "SKILL.md", b"line1\nline2\n")
    _write(mac / "SKILL.md", b"line1\rline2\r")
    assert hash_dir(unix) == hash_dir(mac)


def test_binary_files_are_not_normalized(tmp_path: Path) -> None:
    unix = tmp_path / "unix"
    windows = tmp_path / "windows"
    payload = b"\x00\x01\r\n\r\n"
    _write(unix / "blob.bin", payload)
    _write(windows / "blob.bin", payload)
    assert hash_dir(unix) == hash_dir(windows)


def test_binary_differs_from_text(tmp_path: Path) -> None:
    directory = tmp_path / "a"
    _write(directory / "blob.bin", b"\x00\x01\r\n")
    binary = hash_file(directory / "blob.bin")
    _write(directory / "blob.bin", b"\x00\x01\n")
    assert binary != hash_file(directory / "blob.bin")


def test_excluded_paths_do_not_change_hash(tmp_path: Path) -> None:
    directory = tmp_path / "a"
    _write(directory / "SKILL.md", b"hello\n")
    before = hash_dir(directory)
    _write(directory / "__pycache__" / "x.pyc", b"\x00compiled")
    _write(directory / ".git" / "HEAD", b"ref: refs/heads/main")
    _write(directory / ".DS_Store", b"\x00")
    assert hash_dir(directory) == before


def test_capability_yaml_is_part_of_the_hash(tmp_path: Path) -> None:
    directory = tmp_path / "a"
    _write(directory / "SKILL.md", b"hello\n")
    before = hash_dir(directory)
    _write(directory / "capability.yaml", b"version: 1\n")
    assert hash_dir(directory) != before


def test_path_order_does_not_matter(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    _write(first / "z.txt", b"z\n")
    _write(first / "a.txt", b"a\n")
    _write(second / "a.txt", b"a\n")
    _write(second / "z.txt", b"z\n")
    assert hash_dir(first) == hash_dir(second)


def test_hash_is_stable_across_calls(tmp_path: Path) -> None:
    directory = tmp_path / "a"
    _write(directory / "SKILL.md", b"hello\n")
    assert hash_dir(directory) == hash_dir(directory)
    assert hash_dir(directory).startswith("sha256:")
