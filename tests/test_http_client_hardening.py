"""Tests for the shared transport-hardening layer (CORE-3, v1.33.0).

Covers build_default_ssl_context / build_hardened_async_client directly, and
AS4TransportClient.send()'s adoption of that layer (TLS floor + 429/503
retry), so the two former call sites duplicating (or, for AS4, omitting)
this hardening stay in sync.
"""

from __future__ import annotations

import ssl
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.http_client import (
    build_default_ssl_context,
    build_hardened_async_client,
)
from mcp_einvoicing_core.peppol.transport.client import AS4TransportClient
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.models import AS4Credentials


def _generate_test_pem_cert_and_key() -> tuple[bytes, bytes]:
    """Return (cert_pem, key_pem) for a self-signed test certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test AP")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


SAMPLE_INVOICE = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
  <ID>INV-001</ID>
</Invoice>"""


def _make_receipt_xml(message_id: str = "rcpt-001", ref_to: str = "msg-001") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<S12:Envelope xmlns:S12="http://www.w3.org/2003/05/soap-envelope"
              xmlns:eb="http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/">
  <S12:Header>
    <eb:Messaging>
      <eb:SignalMessage>
        <eb:MessageInfo>
          <eb:Timestamp>2026-06-25T10:00:00Z</eb:Timestamp>
          <eb:MessageId>{message_id}</eb:MessageId>
          <eb:RefToMessageId>{ref_to}</eb:RefToMessageId>
        </eb:MessageInfo>
        <eb:Receipt/>
      </eb:SignalMessage>
    </eb:Messaging>
  </S12:Header>
  <S12:Body/>
</S12:Envelope>""".encode()


def _make_envelope(message_id: str) -> AS4MessageEnvelope:
    return AS4MessageEnvelope(
        sender_id="POP000001",
        receiver_id="0204:991-1234512345-06",
        document_type_id="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice",
        process_id="urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
        payload_xml=SAMPLE_INVOICE,
        message_id=message_id,
    )


class TestBuildDefaultSslContext:
    def test_returns_ssl_context(self) -> None:
        assert isinstance(build_default_ssl_context(), ssl.SSLContext)

    def test_minimum_tls_version_is_1_2(self) -> None:
        assert build_default_ssl_context().minimum_version == ssl.TLSVersion.TLSv1_2

    def test_builds_a_fresh_context_each_call(self) -> None:
        assert build_default_ssl_context() is not build_default_ssl_context()


class TestBuildHardenedAsyncClient:
    def test_returns_async_client(self) -> None:
        client = build_hardened_async_client(
            "https://example.org/as4", timeout=10.0, ssl_context=build_default_ssl_context()
        )
        assert isinstance(client, httpx.AsyncClient)

    def test_trust_env_is_false(self) -> None:
        client = build_hardened_async_client(
            "https://example.org/as4", timeout=10.0, ssl_context=build_default_ssl_context()
        )
        assert client._trust_env is False

    def test_no_pin_hook_when_host_not_pinned(self) -> None:
        client = build_hardened_async_client(
            "https://unpinned.example.org/as4",
            timeout=10.0,
            ssl_context=build_default_ssl_context(),
        )
        assert client.event_hooks.get("response", []) == []

    def test_pin_hook_registered_when_host_is_pinned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import mcp_einvoicing_core.http_client as http_client_module

        monkeypatch.setattr(
            http_client_module,
            "_CERT_PINS",
            {"pinned.example.org": frozenset({"deadbeef"})},
        )
        client = build_hardened_async_client(
            "https://pinned.example.org/as4",
            timeout=10.0,
            ssl_context=build_default_ssl_context(),
        )
        assert len(client.event_hooks.get("response", [])) == 1


class TestAS4TransportClientRetry:
    async def test_retries_on_503_then_succeeds(self, httpx_mock) -> None:
        cert_pem, key_pem = _generate_test_pem_cert_and_key()
        credentials = AS4Credentials(certificate_bytes=cert_pem, private_key_bytes=key_pem)
        envelope = _make_envelope("test-msg-retry")

        httpx_mock.add_response(status_code=503, headers={"Retry-After": "0"})
        httpx_mock.add_response(content=_make_receipt_xml(ref_to="test-msg-retry"))

        client = AS4TransportClient(max_retries=2)
        receipt = await client.send(envelope, "https://ap.example.org/as4", credentials)

        assert receipt.ref_to_message_id == "test-msg-retry"
        assert len(httpx_mock.get_requests()) == 2

    async def test_gives_up_after_max_retries(self, httpx_mock) -> None:
        cert_pem, key_pem = _generate_test_pem_cert_and_key()
        credentials = AS4Credentials(certificate_bytes=cert_pem, private_key_bytes=key_pem)
        envelope = _make_envelope("test-msg-exhausted")

        for _ in range(3):
            httpx_mock.add_response(status_code=503, headers={"Retry-After": "0"})

        client = AS4TransportClient(max_retries=2)
        with pytest.raises(PlatformError):
            await client.send(envelope, "https://ap.example.org/as4", credentials)

        assert len(httpx_mock.get_requests()) == 3
