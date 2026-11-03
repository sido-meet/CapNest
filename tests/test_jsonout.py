"""`--json` 输出的形状。"""

from __future__ import annotations

import io
import json

from capnest.jsonout import error_envelope, success_envelope, write_json


def test_success_envelope_shape():
    envelope = success_envelope("list", {"count": 1})
    assert envelope == {"ok": True, "command": "list", "data": {"count": 1}}


def test_error_envelope_shape():
    envelope = error_envelope("apply", "CONFLICT", "拒绝写入", {"path": "p"})
    assert envelope["ok"] is False
    assert envelope["command"] == "apply"
    assert envelope["error"] == {
        "code": "CONFLICT",
        "message": "拒绝写入",
        "details": {"path": "p"},
    }


def test_error_details_never_missing():
    assert error_envelope("apply", "ERROR", "x")["error"]["details"] == {}


def test_write_json_is_pure_ascii():
    """非 ASCII 一律转义，保证任何控制台编码下都是有效字节。"""
    buffer = io.StringIO()
    write_json(success_envelope("list", {"name": "中文"}), buffer)
    text = buffer.getvalue()
    assert text.isascii()
    assert json.loads(text)["data"]["name"] == "中文"
