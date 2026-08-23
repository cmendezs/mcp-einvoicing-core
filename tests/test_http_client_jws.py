"""Tests for AuthMode.JWS support in mcp_einvoicing_core.http_client."""

from __future__ import annotations

import base64
import datetime
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from joserfc.jwk import RSAKey

from mcp_einvoicing_core.digital_signature import _load_pkcs12
from mcp_einvoicing_core.http_client import (
    AuthMode,
    BaseEInvoicingClient,
    JWSConfig,
    _sign_jws_token,
)


def _decode_registry():
    """A JWSRegistry with a larger header-size cap for test-side verification.

    The x5c header embeds a full certificate, comfortably over joserfc's
    default 512-byte decode guard. Production code never decodes its own
    minted tokens (the receiving platform does), so this override is test-only.
    """
    from joserfc._rfc7515.registry import JWSRegistry

    registry = JWSRegistry(algorithms=["RS256"])
    registry.max_header_length = 8192
    return registry


# ---------------------------------------------------------------------------
# Fixture: self-signed PKCS#12 cert (same pattern as test_http_client_mtls.py)
# ---------------------------------------------------------------------------


def _generate_test_p12(path: Path, password: bytes | None = b"test") -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Test JWS Client")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365)
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
    p = tmp_path / "jws_client.p12"
    _generate_test_p12(p, password=b"test")
    return p


# ---------------------------------------------------------------------------
# Tests for _sign_jws_token
# ---------------------------------------------------------------------------


class TestSignJwsToken:
    def test_header_has_typ_alg_x5c(self, p12_path: Path) -> None:
        from joserfc import jwt as jose_jwt

        cert_info = _load_pkcs12(str(p12_path), "test")
        now = int(time.time())
        token = _sign_jws_token(
            cert_info, "RS256", {}, {"iat": now, "exp": now + 300}
        )
        decoded = jose_jwt.decode(token, RSAKey.import_key(cert_info.private_key.public_key()), registry=_decode_registry())
        assert decoded.header["typ"] == "JWT"
        assert decoded.header["alg"] == "RS256"
        assert decoded.header["x5c"] == [base64.b64encode(cert_info.cert_der).decode("ascii")]

    def test_claims_round_trip(self, p12_path: Path) -> None:
        from joserfc import jwt as jose_jwt

        cert_info = _load_pkcs12(str(p12_path), "test")
        now = int(time.time())
        claims = {"iat": now, "exp": now + 300, "username": "abc123"}
        token = _sign_jws_token(cert_info, "RS256", {}, claims)
        decoded = jose_jwt.decode(token, RSAKey.import_key(cert_info.private_key.public_key()), registry=_decode_registry())
        assert decoded.claims["username"] == "abc123"
        assert decoded.claims["iat"] == now
        assert decoded.claims["exp"] == now + 300

    def test_extra_header_merged(self, p12_path: Path) -> None:
        from joserfc import jwt as jose_jwt

        cert_info = _load_pkcs12(str(p12_path), "test")
        token = _sign_jws_token(cert_info, "RS256", {"kid": "test-kid"}, {"iat": 1, "exp": 2})
        decoded = jose_jwt.decode(token, RSAKey.import_key(cert_info.private_key.public_key()), registry=_decode_registry())
        assert decoded.header["kid"] == "test-kid"

    def test_signature_verifiable(self, p12_path: Path) -> None:
        """A tampered token must fail verification against the real public key."""
        from joserfc import jwt as jose_jwt
        from joserfc.errors import BadSignatureError

        cert_info = _load_pkcs12(str(p12_path), "test")
        token = _sign_jws_token(cert_info, "RS256", {}, {"iat": 1, "exp": 2})
        tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
        with pytest.raises(BadSignatureError):
            jose_jwt.decode(tampered, RSAKey.import_key(cert_info.private_key.public_key()), registry=_decode_registry())


# ---------------------------------------------------------------------------
# Tests for JWSConfig
# ---------------------------------------------------------------------------


class TestJWSConfig:
    def test_defaults(self) -> None:
        config = JWSConfig(cert_path="/some/path.p12")
        assert config.cert_password is None
        assert config.ttl_seconds == 300
        assert config.algorithm == "RS256"
        assert config.extra_claims == {}
        assert config.extra_header == {}

    def test_extra_claims_and_header(self) -> None:
        config = JWSConfig(
            cert_path="/some/path.p12",
            extra_claims={"username": "sha1hex"},
            extra_header={"kid": "1"},
        )
        assert config.extra_claims == {"username": "sha1hex"}
        assert config.extra_header == {"kid": "1"}


# ---------------------------------------------------------------------------
# Tests for BaseEInvoicingClient with AuthMode.JWS
# ---------------------------------------------------------------------------


class TestBaseEInvoicingClientJws:
    def test_jws_requires_jws_config(self) -> None:
        with pytest.raises(ValueError, match="jws_config is required"):
            BaseEInvoicingClient(base_url="https://example.com", auth_mode=AuthMode.JWS)

    def test_jws_instantiation_with_config(self, p12_path: Path) -> None:
        config = JWSConfig(cert_path=str(p12_path), cert_password="test")
        client = BaseEInvoicingClient(
            base_url="https://example.com", auth_mode=AuthMode.JWS, jws_config=config
        )
        assert client._auth_mode == AuthMode.JWS
        assert client._jws_config is config

    @pytest.mark.asyncio
    async def test_headers_authorization_bearer_in_process_fallback(
        self, p12_path: Path
    ) -> None:
        """When the signer microservice is not configured, mint in-process."""
        from joserfc import jwt as jose_jwt

        config = JWSConfig(cert_path=str(p12_path), cert_password="test")
        client = BaseEInvoicingClient(
            base_url="https://example.com", auth_mode=AuthMode.JWS, jws_config=config
        )

        with patch(
            "mcp_einvoicing_core.signer_client.SignerClient.is_configured",
            return_value=False,
        ):
            headers = await client._get_headers()

        assert headers["Authorization"].startswith("Bearer ")
        token = headers["Authorization"].removeprefix("Bearer ")
        cert_info = _load_pkcs12(str(p12_path), "test")
        decoded = jose_jwt.decode(token, RSAKey.import_key(cert_info.private_key.public_key()), registry=_decode_registry())
        assert decoded.header["alg"] == "RS256"
        assert "x5c" in decoded.header

    @pytest.mark.asyncio
    async def test_token_cached_across_calls(self, p12_path: Path) -> None:
        config = JWSConfig(cert_path=str(p12_path), cert_password="test")
        client = BaseEInvoicingClient(
            base_url="https://example.com", auth_mode=AuthMode.JWS, jws_config=config
        )

        with patch(
            "mcp_einvoicing_core.signer_client.SignerClient.is_configured",
            return_value=False,
        ):
            with patch.object(
                client, "_mint_jws_token", wraps=client._mint_jws_token
            ) as mint_spy:
                token1 = await client._get_bearer_token()
                token2 = await client._get_bearer_token()

        assert token1 == token2
        mint_spy.assert_called_once()

    @pytest.mark.asyncio
    async def test_routes_through_signer_client_when_configured(
        self, p12_path: Path
    ) -> None:
        config = JWSConfig(
            cert_path=str(p12_path),
            cert_password="test",
            extra_claims={"username": "abc"},
        )
        client = BaseEInvoicingClient(
            base_url="https://example.com", auth_mode=AuthMode.JWS, jws_config=config
        )

        mock_signer = AsyncMock()
        mock_signer.sign_jws = AsyncMock(return_value="signer.issued.token")

        with patch(
            "mcp_einvoicing_core.signer_client.SignerClient.is_configured",
            return_value=True,
        ):
            with patch(
                "mcp_einvoicing_core.signer_client.SignerClient.from_env",
                return_value=mock_signer,
            ):
                token, ttl = await client._mint_jws_token()

        assert token == "signer.issued.token"
        assert ttl == 300
        mock_signer.sign_jws.assert_called_once()
        call_kwargs = mock_signer.sign_jws.call_args
        claims = call_kwargs.args[0]
        assert claims["username"] == "abc"
        assert "iat" in claims and "exp" in claims
