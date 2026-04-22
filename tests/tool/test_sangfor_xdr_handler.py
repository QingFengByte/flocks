"""Targeted tests for the Sangfor XDR plugin handler.

The handler lives under ``.flocks/plugins/tools/api/sangfor_xdr/`` and is
loaded dynamically at runtime, so we import it via a path-based loader to
exercise the helpers we just hardened:

* ``_resolve_runtime_config`` strips protocol prefixes / inline ports from
  the user-supplied ``host`` so the WebUI ``host=https://10.0.0.1`` value
  stops producing ``https://https://10.0.0.1``.
* ``_decode_auth_code`` raises a friendly error instead of a cryptic
  ``binascii.Error`` when the user pastes a non-hex secret.
* ``_parse_response_body`` falls back through UTF-8 / GBK so the test-
  credentials probe no longer fails with
  ``'utf-8' codec can't decode byte 0x8d in position 0``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

_HANDLER_PATH = (
    Path(__file__).resolve().parents[2]
    / ".flocks"
    / "plugins"
    / "tools"
    / "api"
    / "sangfor_xdr"
    / "sangfor_xdr.handler.py"
)


def _load_handler_module():
    if not _HANDLER_PATH.exists():
        pytest.skip(f"Sangfor XDR handler not present at {_HANDLER_PATH}")
    spec = importlib.util.spec_from_file_location(
        "_sangfor_xdr_handler_under_test",
        str(_HANDLER_PATH),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def handler():
    return _load_handler_module()


# ---------------------------------------------------------------------------
# Host normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_host, expected_base_url",
    [
        ("10.0.0.1", "https://10.0.0.1"),
        ("https://10.0.0.1", "https://10.0.0.1"),
        ("https://10.0.0.1/", "https://10.0.0.1"),
        ("http://10.0.0.1", "https://10.0.0.1"),
        ("HTTPS://example.test", "https://example.test"),
        ("10.0.0.1:8443", "https://10.0.0.1:8443"),
        ("https://10.0.0.1:8443/", "https://10.0.0.1:8443"),
    ],
)
def test_resolve_runtime_config_normalises_host(handler, raw_host, expected_base_url):
    fake_secret_manager = type(
        "_SM",
        (),
        {"get": staticmethod(lambda key: "deadbeef" if "auth_code" in key else None)},
    )()

    raw_cfg: dict[str, Any] = {
        "host": raw_host,
        "auth_code": "deadbeef",
        "verify_ssl": False,
    }

    with (
        patch.object(handler.ConfigWriter, "get_api_service_raw", return_value=raw_cfg),
        patch.object(handler, "_get_secret_manager", return_value=fake_secret_manager),
    ):
        cfg = handler._resolve_runtime_config()

    assert cfg.base_url == expected_base_url
    assert cfg.verify_ssl is False
    assert cfg.auth_code == "deadbeef"


# ---------------------------------------------------------------------------
# auth_code decoding
# ---------------------------------------------------------------------------

def test_decode_auth_code_rejects_non_hex(handler):
    handler._AK_SK_CACHE.clear()
    with pytest.raises(ValueError) as exc:
        handler._decode_auth_code("lxy/FS$)K10R822_v1WRt)$n")
    assert "联动码" in str(exc.value) or "hex" in str(exc.value).lower()


def test_decode_auth_code_rejects_empty(handler):
    handler._AK_SK_CACHE.clear()
    with pytest.raises(ValueError):
        handler._decode_auth_code("")


# ---------------------------------------------------------------------------
# Response body parsing
# ---------------------------------------------------------------------------

def test_parse_response_body_utf8(handler):
    body = json.dumps({"code": "Success", "data": {"hello": "世界"}}).encode("utf-8")
    parsed = handler._parse_response_body(body, 200)
    assert parsed["code"] == "Success"
    assert parsed["data"]["hello"] == "世界"


def test_parse_response_body_gbk_fallback(handler):
    body = json.dumps({"code": "Success", "msg": "成功"}, ensure_ascii=False).encode("gbk")
    # The first byte of "成" in GBK is 0xB3 — not the canonical 0x8d that
    # broke the user's setup, but the same code path handles every leading
    # byte that fails strict UTF-8 validation.
    parsed = handler._parse_response_body(body, 200)
    assert parsed["msg"] == "成功"


def test_parse_response_body_does_not_leak_unicode_decode_error(handler):
    """Reproduces the user's symptom: a body that fails strict UTF-8 must
    surface as a deterministic ``RuntimeError`` rather than the raw
    ``'utf-8' codec can't decode byte 0x8d in position 0`` ``UnicodeError``
    bubbling out of ``aiohttp``."""

    body = bytes([0x8D, 0xFF, 0xFE, 0xC0])  # not a valid prefix in any encoding+JSON
    with pytest.raises(UnicodeDecodeError):
        body.decode("utf-8")

    with pytest.raises(RuntimeError) as exc:
        handler._parse_response_body(body, 200)

    # Crucially: it is *not* a UnicodeDecodeError — operators see a clear
    # XDR-specific message instead of an opaque codec failure.
    assert not isinstance(exc.value, UnicodeDecodeError)


def test_parse_response_body_empty_raises(handler):
    with pytest.raises(RuntimeError) as exc:
        handler._parse_response_body(b"", 502)
    assert "empty body" in str(exc.value)
    assert "502" in str(exc.value)


def test_parse_response_body_undecodable_raises(handler):
    raw = bytes([0x8D, 0xFF, 0xFE, 0xC0])
    with pytest.raises(RuntimeError) as exc:
        handler._parse_response_body(raw, 200)
    assert "could not decode" in str(exc.value).lower() or "parse" in str(exc.value).lower()
