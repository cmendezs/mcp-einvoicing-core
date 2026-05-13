"""Tests for mcp_einvoicing_core.qr."""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest

from mcp_einvoicing_core.qr import generate_qr_png_base64

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class TestGenerateQrPngBase64:
    def test_returns_base64_string(self) -> None:
        result = generate_qr_png_base64("https://example.com")
        assert isinstance(result, str)
        # Must be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_output_is_valid_png(self) -> None:
        result = generate_qr_png_base64("https://example.com")
        decoded = base64.b64decode(result)
        assert decoded[:8] == PNG_MAGIC

    def test_encodes_url(self) -> None:
        url = (
            "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR"
            "?nif=B12345678&numserie=2025-0001&fecha=15-03-2025&importe=1210.00"
        )
        result = generate_qr_png_base64(url)
        assert base64.b64decode(result)[:8] == PNG_MAGIC

    def test_encodes_plain_text(self) -> None:
        result = generate_qr_png_base64("HELLO WORLD")
        assert base64.b64decode(result)[:8] == PNG_MAGIC

    def test_all_error_correction_levels(self) -> None:
        for level in ("L", "M", "Q", "H"):
            result = generate_qr_png_base64("test", error_correction=level)
            assert base64.b64decode(result)[:8] == PNG_MAGIC

    def test_invalid_error_correction_raises(self) -> None:
        with pytest.raises(ValueError, match="error_correction must be one of"):
            generate_qr_png_base64("test", error_correction="X")

    def test_size_px_affects_output_size(self) -> None:
        small = base64.b64decode(generate_qr_png_base64("test", size_px=50))
        large = base64.b64decode(generate_qr_png_base64("test", size_px=400))
        # Larger box_size produces a larger file
        assert len(large) > len(small)

    def test_no_data_url_prefix(self) -> None:
        result = generate_qr_png_base64("test")
        assert not result.startswith("data:")

    def test_missing_qrcode_raises_import_error(self) -> None:
        with patch.dict("sys.modules", {"qrcode": None}):
            with pytest.raises(ImportError, match="qrcode\\[pil\\]"):
                generate_qr_png_base64("test")
