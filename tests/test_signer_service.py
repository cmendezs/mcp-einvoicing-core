"""Tests for the signer microservice's mTLS submit retry behaviour.

_do_mtls_submit is the out-of-process counterpart to BaseEInvoicingClient's
in-process _request: it must retry 429/503 the same way, since it is the
recommended (non-legacy) submission path for every country package that uses
SignerClient. Reuses the p12-generation fixture pattern from
test_http_client_mtls.py.
"""

from __future__ import annotations

import base64
import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_einvoicing_core.signer_service import _SignerService


def _generate_test_p12(path: Path, password: bytes | None = b"test") -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        )
        .sign(key, hashes.SHA256())
    )
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=(
            serialization.BestAvailableEncryption(password)
            if password
            else serialization.NoEncryption()
        ),
    )
    path.write_bytes(p12_bytes)


@pytest.fixture()
def signer(tmp_path: Path) -> _SignerService:
    p12_path = tmp_path / "signer.p12"
    _generate_test_p12(p12_path, password=b"test")
    return _SignerService(
        cert_path=str(p12_path),
        cert_password="test",
        token="test-token",
        socket_path=str(tmp_path / "signer.sock"),
    )


def _response(status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code, headers=headers or {}, content=b'{"ok": true}')


@pytest.mark.asyncio
async def test_mtls_submit_no_retry_on_success(signer: _SignerService) -> None:
    mock_post = AsyncMock(return_value=_response(200))
    with patch("httpx.AsyncClient.post", mock_post), patch("asyncio.sleep", AsyncMock()):
        result = await signer._do_mtls_submit(
            {"url": "https://example.test/submit", "payload_b64": base64.b64encode(b"<xml/>").decode()}
        )

    assert result["result"]["status_code"] == 200
    assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_mtls_submit_retries_on_503_then_succeeds(signer: _SignerService) -> None:
    mock_post = AsyncMock(side_effect=[_response(503), _response(503), _response(200)])
    sleep_mock = AsyncMock()
    with patch("httpx.AsyncClient.post", mock_post), patch("asyncio.sleep", sleep_mock):
        result = await signer._do_mtls_submit(
            {"url": "https://example.test/submit", "payload_b64": base64.b64encode(b"<xml/>").decode()}
        )

    assert result["result"]["status_code"] == 200
    assert mock_post.call_count == 3
    assert sleep_mock.call_count == 2


@pytest.mark.asyncio
async def test_mtls_submit_retries_on_429_respects_retry_after(signer: _SignerService) -> None:
    mock_post = AsyncMock(
        side_effect=[_response(429, headers={"Retry-After": "7"}), _response(200)]
    )
    sleep_mock = AsyncMock()
    with patch("httpx.AsyncClient.post", mock_post), patch("asyncio.sleep", sleep_mock):
        result = await signer._do_mtls_submit(
            {"url": "https://example.test/submit", "payload_b64": base64.b64encode(b"<xml/>").decode()}
        )

    assert result["result"]["status_code"] == 200
    sleep_mock.assert_awaited_once_with(7.0)


@pytest.mark.asyncio
async def test_mtls_submit_returns_last_response_when_retries_exhausted(
    signer: _SignerService,
) -> None:
    # DEFAULT_MAX_RETRIES=3 → 4 total attempts, all 503.
    mock_post = AsyncMock(return_value=_response(503))
    with patch("httpx.AsyncClient.post", mock_post), patch("asyncio.sleep", AsyncMock()):
        result = await signer._do_mtls_submit(
            {"url": "https://example.test/submit", "payload_b64": base64.b64encode(b"<xml/>").decode()}
        )

    assert result["result"]["status_code"] == 503
    assert mock_post.call_count == 4


@pytest.mark.asyncio
async def test_mtls_submit_files_variant_also_retries(signer: _SignerService) -> None:
    mock_post = AsyncMock(side_effect=[_response(429), _response(200)])
    with patch("httpx.AsyncClient.post", mock_post), patch("asyncio.sleep", AsyncMock()):
        result = await signer._do_mtls_submit(
            {
                "url": "https://example.test/submit",
                "files": [
                    {
                        "name": "xml",
                        "filename": "registro.xml",
                        "content_b64": base64.b64encode(b"<xml/>").decode(),
                        "mime": "application/xml",
                    }
                ],
            }
        )

    assert result["result"]["status_code"] == 200
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_mtls_submit_does_not_retry_on_other_error_codes(signer: _SignerService) -> None:
    mock_post = AsyncMock(return_value=_response(400))
    with patch("httpx.AsyncClient.post", mock_post), patch("asyncio.sleep", AsyncMock()):
        result = await signer._do_mtls_submit(
            {"url": "https://example.test/submit", "payload_b64": base64.b64encode(b"<xml/>").decode()}
        )

    assert result["result"]["status_code"] == 400
    assert mock_post.call_count == 1
