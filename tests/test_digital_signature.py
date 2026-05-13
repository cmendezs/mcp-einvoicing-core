"""Tests for mcp_einvoicing_core.digital_signature."""

from __future__ import annotations

import base64
import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree

from mcp_einvoicing_core.digital_signature import (
    XAdESEPESSigner,
    XAdESSignerConfig,
    _DS,
    _XADES,
)

# ---------------------------------------------------------------------------
# Fixture: self-signed PKCS#12 cert generated with cryptography
# ---------------------------------------------------------------------------


def _generate_test_p12(path: Path, password: bytes | None = b"test") -> None:
    """Write a minimal self-signed RSA cert as PKCS#12 to *path*."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer")]
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
    """Return path to a temporary PKCS#12 file (password: 'test')."""
    p = tmp_path / "cert.p12"
    _generate_test_p12(p, password=b"test")
    return p


@pytest.fixture()
def p12_path_no_password(tmp_path: Path) -> Path:
    """Return path to a temporary PKCS#12 file with no password."""
    p = tmp_path / "cert_nopass.p12"
    _generate_test_p12(p, password=None)
    return p


SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Facturae xmlns="http://www.facturae.es/Facturae/2009/v3.2/Facturae">
  <FileHeader><SchemaVersion>3.2.2</SchemaVersion></FileHeader>
  <Parties/>
  <Invoices/>
</Facturae>
"""

POLICY_ID = "http://www.facturae.es/politica_de_firma_formato_facturae/v3_1.pdf"
POLICY_HASH = base64.b64encode(b"\x00" * 32).decode()  # dummy hash for tests


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestXAdESEPESSigner:
    def test_returns_xml_bytes(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        assert isinstance(result, bytes)

    def test_output_is_valid_xml(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        assert root is not None

    def test_signature_element_present(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        sigs = root.findall(f"{{{_DS}}}Signature")
        assert len(sigs) == 1

    def test_signature_value_is_non_empty_base64(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        sig = root.find(f"{{{_DS}}}Signature")
        assert sig is not None
        sv = sig.find(f"{{{_DS}}}SignatureValue")
        assert sv is not None and sv.text
        decoded = base64.b64decode(sv.text)
        assert len(decoded) > 0

    def test_key_info_contains_certificate(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        sig = root.find(f"{{{_DS}}}Signature")
        assert sig is not None
        ki = sig.find(f"{{{_DS}}}KeyInfo")
        assert ki is not None
        x509 = ki.find(f".//{{{_DS}}}X509Certificate")
        assert x509 is not None and x509.text
        base64.b64decode(x509.text)  # must be valid base64

    def test_qualifying_properties_present(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        qp = root.find(f".//{{{_XADES}}}QualifyingProperties")
        assert qp is not None

    def test_signing_time_present_and_parseable(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        st = root.find(f".//{{{_XADES}}}SigningTime")
        assert st is not None and st.text
        # Must parse as UTC ISO 8601
        datetime.datetime.strptime(st.text, "%Y-%m-%dT%H:%M:%SZ")

    def test_signature_policy_included_when_configured(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(
            cert_path=str(p12_path),
            cert_password="test",
            signature_policy_id=POLICY_ID,
            signature_policy_hash=POLICY_HASH,
        )
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        spi = root.find(f".//{{{_XADES}}}SignaturePolicyIdentifier")
        assert spi is not None
        identifier = spi.find(f".//{{{_XADES}}}Identifier")
        assert identifier is not None and identifier.text == POLICY_ID

    def test_no_policy_when_not_configured(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        spi = root.find(f".//{{{_XADES}}}SignaturePolicyIdentifier")
        assert spi is None

    def test_claimed_role_included_when_set(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(
            cert_path=str(p12_path),
            cert_password="test",
            claimed_role="supplier",
        )
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        cr = root.find(f".//{{{_XADES}}}ClaimedRole")
        assert cr is not None and cr.text == "supplier"

    def test_no_password_cert(self, p12_path_no_password: Path) -> None:
        config = XAdESSignerConfig(
            cert_path=str(p12_path_no_password), cert_password=None
        )
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        assert root.find(f"{{{_DS}}}Signature") is not None

    def test_original_content_preserved(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        # The original root tag must still be present
        assert "Facturae" in root.tag

    def test_signed_info_references_document_and_signed_properties(
        self, p12_path: Path
    ) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        sig = root.find(f"{{{_DS}}}Signature")
        assert sig is not None
        si = sig.find(f"{{{_DS}}}SignedInfo")
        assert si is not None
        refs = si.findall(f"{{{_DS}}}Reference")
        assert len(refs) == 2
        uris = {r.get("URI", "") for r in refs}
        assert "" in uris  # empty URI = enveloped document reference

    def test_missing_cryptography_raises_import_error(self, p12_path: Path) -> None:
        with patch.dict("sys.modules", {"cryptography": None,
                                        "cryptography.hazmat": None,
                                        "cryptography.hazmat.primitives": None,
                                        "cryptography.hazmat.primitives.serialization": None,
                                        "cryptography.hazmat.primitives.serialization.pkcs12": None}):
            config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
            signer = XAdESEPESSigner(config)
            signer._cert_info = None  # force reload
            with pytest.raises(ImportError, match="cryptography"):
                signer.sign(SAMPLE_XML)
