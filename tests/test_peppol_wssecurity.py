"""Tests for WS-Security X.509 signing of outbound AS4 messages (AS4-SIGN-1)."""

from __future__ import annotations

import base64
import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from mcp_einvoicing_core.peppol.transport.wssecurity import (
    _DS_NS,
    _EBMS_NS,
    _SOAP_NS,
    _WSSE_NS,
    _WSU_NS,
    SignedAttachment,
    _exc_c14n,
    sign_as4_message,
    verify_as4_signature,
)


def _generate_test_key_and_cert() -> tuple[rsa.RSAPrivateKey, bytes]:
    """Return (private_key, der_cert_bytes) for a self-signed test certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test AP")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return key, cert.public_bytes(serialization.Encoding.DER)


@pytest.fixture()
def key_and_cert() -> tuple[rsa.RSAPrivateKey, bytes]:
    return _generate_test_key_and_cert()


_SAMPLE_SOAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<S12:Envelope xmlns:S12="http://www.w3.org/2003/05/soap-envelope"
              xmlns:eb="http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/">
  <S12:Header>
    <eb:Messaging>
      <eb:UserMessage>
        <eb:MessageInfo>
          <eb:MessageId>test-msg-001</eb:MessageId>
        </eb:MessageInfo>
      </eb:UserMessage>
    </eb:Messaging>
  </S12:Header>
  <S12:Body/>
</S12:Envelope>"""


class TestSignAs4Message:
    def test_inserts_wsse_security_header(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)

        security = root.find(f".//{{{_WSSE_NS}}}Security")
        assert security is not None
        assert security.get(f"{{{_SOAP_NS}}}mustUnderstand") == "true"

    def test_binary_security_token_carries_certificate(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)

        bst = root.find(f".//{{{_WSSE_NS}}}BinarySecurityToken")
        assert bst is not None
        assert bst.get("ValueType").endswith("#X509v3")
        assert base64.b64decode(bst.text) == cert_der

    def test_signature_has_three_references(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)

        refs = root.findall(f".//{{{_DS_NS}}}Reference")
        assert len(refs) == 3
        uris = {r.get("URI") for r in refs}
        assert "cid:invoice@peppol.eu" in uris
        body_or_messaging_uris = [u for u in uris if u.startswith("#")]
        assert len(body_or_messaging_uris) == 2

    def test_attachment_reference_digests_raw_bytes(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        import hashlib

        key, cert_der = key_and_cert
        content = b"payload-bytes-for-digest-check"
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=content)]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)

        for ref in root.findall(f".//{{{_DS_NS}}}Reference"):
            if ref.get("URI") == "cid:invoice@peppol.eu":
                digest_el = ref.find(f"{{{_DS_NS}}}DigestValue")
                expected = base64.b64encode(hashlib.sha256(content).digest()).decode()
                assert digest_el.text == expected

    def test_body_and_messaging_get_wsu_id(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"x")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)

        body = root.find(f".//{{{_SOAP_NS}}}Body")
        messaging = root.find(f".//{{{_EBMS_NS}}}Messaging")
        assert body.get(f"{{{_WSU_NS}}}Id") is not None
        assert messaging.get(f"{{{_WSU_NS}}}Id") is not None

    def test_signature_value_verifies_cryptographically(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)

        signed_info = root.find(f".//{{{_DS_NS}}}SignedInfo")
        signature_value_b64 = root.find(f".//{{{_DS_NS}}}SignatureValue").text

        public_key = key.public_key()
        public_key.verify(
            base64.b64decode(signature_value_b64),
            _exc_c14n(signed_info),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )  # raises InvalidSignature if verification fails

    def test_key_info_references_bst_by_id(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"x")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)

        bst_id = root.find(f".//{{{_WSSE_NS}}}BinarySecurityToken").get(f"{{{_WSU_NS}}}Id")
        str_ref = root.find(f".//{{{_WSSE_NS}}}SecurityTokenReference/{{{_WSSE_NS}}}Reference")
        assert str_ref.get("URI") == f"#{bst_id}"

    def test_raises_on_missing_messaging_header(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        no_messaging_soap = b"""<?xml version="1.0"?>
<S12:Envelope xmlns:S12="http://www.w3.org/2003/05/soap-envelope">
  <S12:Header/>
  <S12:Body/>
</S12:Envelope>"""
        with pytest.raises(ValueError, match="eb:Messaging"):
            sign_as4_message(no_messaging_soap, [], cert_der, key)


class TestVerifyAs4Signature:
    def test_round_trip_verifies(self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        result = verify_as4_signature(signed, attachments)

        assert result.signature_valid is True
        assert result.certificate_der == cert_der
        assert result.error is None

    def test_missing_security_header(self) -> None:
        result = verify_as4_signature(_SAMPLE_SOAP, [])
        assert result.signature_valid is False
        assert "wsse:Security" in result.error

    def test_tampered_attachment_fails(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)

        tampered_attachments = [
            SignedAttachment(content_id="invoice@peppol.eu", content=b"tampered-bytes")
        ]
        result = verify_as4_signature(signed, tampered_attachments)
        assert result.signature_valid is False
        assert "digest mismatch" in result.error

    def test_tampered_body_fails(self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)
        root = etree.fromstring(signed)
        messaging = root.find(f".//{{{_EBMS_NS}}}Messaging")
        message_id_el = messaging.find(
            f".//{{{_EBMS_NS}}}MessageId"
        )
        message_id_el.text = "tampered-message-id"
        tampered_signed = etree.tostring(root)

        result = verify_as4_signature(tampered_signed, attachments)
        assert result.signature_valid is False

    def test_missing_attachment_fails(
        self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]
    ) -> None:
        key, cert_der = key_and_cert
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]
        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, key)

        result = verify_as4_signature(signed, [])
        assert result.signature_valid is False
        assert "attachment not supplied" in result.error

    def test_wrong_signer_key_fails(self, key_and_cert: tuple[rsa.RSAPrivateKey, bytes]) -> None:
        key, cert_der = key_and_cert
        other_key, _ = _generate_test_key_and_cert()
        attachments = [SignedAttachment(content_id="invoice@peppol.eu", content=b"payload-bytes")]

        # Sign with a different key than the one embedded in the BST.
        signed = sign_as4_message(_SAMPLE_SOAP, attachments, cert_der, other_key)
        result = verify_as4_signature(signed, attachments)
        assert result.signature_valid is False
