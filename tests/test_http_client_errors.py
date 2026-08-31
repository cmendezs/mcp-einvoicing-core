"""Tests for mcp_einvoicing_core.http_client._extract_platform_error."""

from __future__ import annotations

import httpx

from mcp_einvoicing_core.http_client import _extract_platform_error


def _response(status_code: int, content: bytes) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=content,
        request=httpx.Request("POST", "https://example.invalid/x"),
    )


class TestExtractPlatformError:
    def test_status_code_and_message(self) -> None:
        err = _extract_platform_error(_response(404, b""), "not found")
        assert err.status_code == 404
        assert "not found" in str(err)

    def test_error_code_passed_through(self) -> None:
        err = _extract_platform_error(_response(400, b""), "bad request", "ERR_001")
        assert err.error_code == "ERR_001"

    def test_response_body_carries_raw_content(self) -> None:
        body = b'{"exceptionCode": "AUTH_001", "message": "bad token"}'
        err = _extract_platform_error(_response(401, body), "unauthorized")
        assert err.response_body == body

    def test_empty_body_is_empty_bytes_not_none(self) -> None:
        err = _extract_platform_error(_response(500, b""), "server error")
        assert err.response_body == b""
