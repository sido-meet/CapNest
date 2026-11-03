"""隐藏 Unicode 扫描。

Agent 会把 skill 文档原样读进上下文，因此**看不见的字符就是攻击面**：
零宽字符可以藏指令、双向控制符可以骗过人类阅读、Unicode tag 字符可以
在运行时拼出任意 ASCII、同形异义字符可以让 `README` 变成 `README`。

四类命中**一律阻断**（退出码 6），不做「可疑但放行」。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from capnest.util.text import decode_text

#: 零宽字符：看不见，但会改变字符串的实际内容。
ZERO_WIDTH: frozenset[str] = frozenset(
    {
        "\u200b",  # ZERO WIDTH SPACE
        "\u200c",  # ZERO WIDTH NON-JOINER
        "\u200d",  # ZERO WIDTH JOINER
        "\u2028",  # LINE SEPARATOR
        "\u2029",  # PARAGRAPH SEPARATOR
        "\ufeff",  # ZERO WIDTH NO-BREAK SPACE / BOM
        "\u2060",  # WORD JOINER
        "\u180e",  # MONGOLIAN VOWEL SEPARATOR
    }
)

#: 双向控制符：能让渲染顺序与逻辑顺序不一致。
BIDI_CONTROL: frozenset[str] = frozenset(
    {
        "\u200e",  # LEFT-TO-RIGHT MARK
        "\u200f",  # RIGHT-TO-LEFT MARK
        "\u202a",  # LEFT-TO-RIGHT EMBEDDING
        "\u202b",  # RIGHT-TO-LEFT EMBEDDING
        "\u202c",  # POP DIRECTIONAL FORMATTING
        "\u202d",  # LEFT-TO-RIGHT OVERRIDE
        "\u202e",  # RIGHT-TO-LEFT OVERRIDE
        "\u2066",  # LEFT-TO-RIGHT ISOLATE
        "\u2067",  # RIGHT-TO-LEFT ISOLATE
        "\u2068",  # FIRST STRONG ISOLATE
        "\u2069",  # POP DIRECTIONAL ISOLATE
    }
)

#: Unicode tag 字符：在运行时可以拼回任意 ASCII 标签。
TAG_RANGE: tuple[int, int] = (0xE0000, 0xE007F)

#: 同形异义字符 → 它模仿的 ASCII 字母。只收「在正常文本里几乎不会出现」的。
HOMOGLYPHS: dict[str, str] = {
    # 西里尔字母
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
    "ј": "j",
    "ѕ": "s",
    "һ": "h",
    "А": "A",
    "В": "B",
    "Е": "E",
    "К": "K",
    "М": "M",
    "Н": "H",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Т": "T",
    "У": "Y",
    "Х": "X",
    "Ѕ": "S",
    "І": "I",
    "Ј": "J",
    "Ԛ": "Q",
    "Ԝ": "W",
    # 希腊字母
    "α": "a",
    "ε": "e",
    "ι": "i",
    "κ": "k",
    "ν": "v",
    "ο": "o",
    "ρ": "p",
    "τ": "t",
    "υ": "u",
    "χ": "x",
    "Α": "A",
    "Β": "B",
    "Ε": "E",
    "Ζ": "Z",
    "Η": "H",
    "Ι": "I",
    "Κ": "K",
    "Μ": "M",
    "Ν": "N",
    "Ο": "O",
    "Ρ": "P",
    "Τ": "T",
    "Υ": "Y",
    "Χ": "X",
    # 全角 ASCII 字母与数字
    **{chr(code): chr(code - 0xFEE0) for code in range(0xFF21, 0xFF3B)},
    **{chr(code): chr(code - 0xFEE0) for code in range(0xFF41, 0xFF5B)},
    **{chr(code): chr(code - 0xFEE0) for code in range(0xFF10, 0xFF1A)},
}


@dataclass(frozen=True)
class Finding:
    """一处命中。"""

    file: str
    line: int
    column: int
    category: str
    char: str
    codepoint: str
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "category": self.category,
            "char": self.char,
            "codepoint": self.codepoint,
            "detail": self.detail,
        }


def _codepoint(char: str) -> str:
    return f"U+{ord(char):04X}"


def categorize(char: str) -> str | None:
    """判定一个字符属于哪一类隐藏字符；不是则返回 None。"""
    if char in ZERO_WIDTH:
        return "zero-width"
    if char in BIDI_CONTROL:
        return "bidi"
    code = ord(char)
    if TAG_RANGE[0] <= code <= TAG_RANGE[1]:
        return "tag"
    if char in HOMOGLYPHS:
        return "homoglyph"
    return None


def scan_text(text: str, *, file: str = "") -> list[Finding]:
    """扫描一段文本。"""
    findings: list[Finding] = []
    for index, char in enumerate(text):
        category = categorize(char)
        if category is None:
            continue
        line = text.count("\n", 0, index) + 1
        line_start = text.rfind("\n", 0, index) + 1
        column = index - line_start + 1
        detail = ""
        if category == "homoglyph":
            detail = f"模仿 ASCII '{HOMOGLYPHS[char]}'"
        elif category == "tag":
            detail = "Unicode tag 字符，可用于隐藏任意 ASCII"
        elif category == "bidi":
            detail = "双向控制符，渲染顺序与逻辑顺序可能不一致"
        else:
            detail = "零宽字符，不可见但会改变字符串内容"
        findings.append(
            Finding(
                file=file,
                line=line,
                column=column,
                category=category,
                char=char,
                codepoint=_codepoint(char),
                detail=detail,
            )
        )
    return findings


def scan_file(path: Path, *, display: str | None = None) -> list[Finding]:
    """扫描一个文件；二进制文件跳过。"""
    try:
        data = path.read_bytes()
    except OSError:
        return []
    text = decode_text(data)
    if text is None:
        return []
    return scan_text(text, file=display or path.name)


def scan_tree(root: Path, *, base: Path | None = None) -> list[Finding]:
    """扫描一棵目录树里的全部文本文件。"""
    findings: list[Finding] = []
    if not root.exists():
        return findings
    if root.is_file():
        return scan_file(root, display=root.name)
    anchor = base or root
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(anchor).as_posix()
        findings.extend(scan_file(path, display=relative))
    return findings


def describe(char: str) -> str:
    """字符的可读名称。"""
    try:
        return unicodedata.name(char)
    except ValueError:
        return "UNKNOWN"
