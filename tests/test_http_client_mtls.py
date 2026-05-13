"""Tests for MTLS support in mcp_einvoicing_core.http_client."""

from __future__ import annotations

import datetime
import ssl
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_einvoicing_core.http_client import (
    AuthMode,
    BaseEInvoicingClient,
    _build_mtls_ssl_context,
)


# ---------------------------------------------------------------------------
# Fixture: self-signed PKCS#12 cert (reuse pattern from test_digital_signature)
# ---------------------------------------------------------------------------


def _generate_test_p12(path: Path, password: bytes | None = b"test") -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Test MTLS Client")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=365)
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
def p12_path(tmp_path: Path) -> Path:
    p = tmp_path / "client.p12"
    _generate_test_p12(p, password=b"test")
    return p


@pytest.fixture()
def p12_path_no_password(tmp_path: Path) -> Path:
    p = tmp_path / "client_nopass.p12"
    _generate_test_p12(p, password=None)
    return p


# ---------------------------------------------------------------------------
# Tests for _build_mtls_ssl_context
# ---------------------------------------------------------------------------


class TestBuildMtlsSslContext:
    def test_returns_ssl_context(self, p12_path: Path) -> None:
        ctx = _build_mtls_ssl_context(str(p12_path), "test")
        assert isinstance(ctx, ssl.SSLContext)

    def test_no_password(self, p12_path_no_password: Path) -> None:
        ctx = _build_mtls_ssl_context(str(p12_path_no_password), None)
        assert isinstance(ctx, ssl.SSLContext)

    def test_tempfile_cleaned_up(self, p12_path: Path) -> None:
        import glob
        import os

        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.pem")))
        _build_mtls_ssl_context(str(p12_path), "test")
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "*.pem")))
        # No new .pem files should remain after the call
        assert after == before

    def test_wrong_password_raises(self, p12_path: Path) -> None:
        with pytest.raises(Exception):
            _build_mtls_ssl_context(str(p12_path), "wrong-password")

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            _build_mtls_ssl_context("/nonexistent/cert.p12", None)


# ---------------------------------------------------------------------------
# Tests for BaseEInvoicingClient with MTLS
# ---------------------------------------------------------------------------


class TestBaseEInvoicingClientMtls:
    def test_mtls_requires_cert_path(self) -> None:
        with pytest.raises(ValueError, match="cert_path is required"):
            BaseEInvoicingClient(
                base_url="https://example.com",
                auth_mode=AuthMode.MTLS,
            )

    def test_mtls_instantiation_with_cert(self, p12_path: Path) -> None:
        client = BaseEInvoicingClient(
            base_url="https://example.com",
            auth_mode=AuthMode.MTLS,
            cert_path=str(p12_path),
            cert_password="test",
        )
        assert client._auth_mode == AuthMode.MTLS
        assert client._cert_path == str(p12_path)

    def test_mtls_ssl_context_lazy_loaded(self, p12_path: Path) -> None:
        client = BaseEInvoicingClient(
            base_url="https://example.com",
            auth_mode=AuthMode.MTLS,
            cert_path=str(p12_path),
            cert_password="test",
        )
        # Not loaded at init time
        assert client._mtls_ssl_context is None
        # Loaded on first _get_httpx_client() call
        client._get_httpx_client()
        assert client._mtls_ssl_context is not None

    def test_mtls_ssl_context_cached(self, p12_path: Path) -> None:
        client = BaseEInvoicingClient(
            base_url="https://example.com",
            auth_mode=AuthMode.MTLS,
            cert_path=str(p12_path),
            cert_password="test",
        )
        client._get_httpx_client()
        ctx1 = client._mtls_ssl_context
        client._get_httpx_client()
        ctx2 = client._mtls_ssl_context
        # Same SSLContext object reused
        assert ctx1 is ctx2

    def test_non_mtls_client_gets_plain_client(self) -> None:
        import httpx

        client = BaseEInvoicingClient(
            base_url="https://example.com",
            auth_mode=AuthMode.NONE,
        )
        httpx_client = client._get_httpx_client()
        assert isinstance(httpx_client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_mtls_headers_contain_no_authorization(self, p12_path: Path) -> None:
        client = BaseEInvoicingClient(
            base_url="https://example.com",
            auth_mode=AuthMode.MTLS,
            cert_path=str(p12_path),
            cert_password="test",
        )
        headers = await client._get_headers()
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_request_uses_get_httpx_client(self, p12_path: Path) -> None:
        """_request() must call _get_httpx_client() instead of building its own."""
        client = BaseEInvoicingClient(
            base_url="https://example.com",
            auth_mode=AuthMode.MTLS,
            cert_path=str(p12_path),
            cert_password="test",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True

        mock_httpx = AsyncMock()
        mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.request = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_httpx_client", return_value=mock_httpx) as patched:
            await client._request("GET", "/test")
            patched.assert_called_once()
