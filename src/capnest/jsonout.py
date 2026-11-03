"""`--json` 输出协议。

成功：`{"ok": true, "command": "...", "data": {...}}`
失败：`{"ok": false, "command": "...", "error": {"code", "message", "details"}}`

`message` 只给人看，`details` 放机器需要的数据（路径、冲突列表……），
这样 GUI 与 Agent 不必解析自然语言。
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def success_envelope(command: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "command": command, "data": data}


def error_envelope(
    command: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": command,
        "error": {"code": code, "message": message, "details": details or {}},
    }


def write_json(payload: dict[str, Any], stream: TextIO | None = None) -> None:
    """把 envelope 写到 stdout（默认）。

    非 ASCII 字符一律转义成 `\\uXXXX`：JSON 是给机器读的，
    纯 ASCII 在任何控制台编码（UTF-8 / GBK / CP437）下都是有效字节，
    不会出现「终端把 UTF-8 当 GBK 解」这种乱码。
    """
    target = stream if stream is not None else sys.stdout
    json.dump(payload, target, ensure_ascii=True, indent=2, sort_keys=False)
    target.write("\n")
    target.flush()
