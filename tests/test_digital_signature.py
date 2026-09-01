"""Tests for mcp_einvoicing_core.digital_signature."""

from __future__ import annotations

import base64
import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree

from mcp_einvoicing_core.digital_signature import (
    _C14N_ALG,
    _DS,
    _ENVELOPED_TRANSFORM,
    _RSA_SHA256_SIGN_ALG,
    _SHA256_DIGEST_ALG,
    _XADES,
    CAdESSigner,
    CAdESSignerConfig,
    SelloDigitalSigner,
    SelloDigitalSignerConfig,
    XAdESEPESSigner,
    XAdESSignerConfig,
    XMLDSigSigner,
    XMLDSigSignerConfig,
    _load_pkcs12,
    load_certificate_der,
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
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer")])
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

NFE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe Id="NFe35260112345678000199550010000000011000000010" versao="4.00">
    <ide><cUF>35</cUF></ide>
  </infNFe>
</NFe>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadCertificateDer:
    def test_returns_bytes(self, p12_path: Path) -> None:
        der = load_certificate_der(str(p12_path), "test")
        assert isinstance(der, bytes)
        assert len(der) > 0

    def test_matches_load_pkcs12_cert_der(self, p12_path: Path) -> None:
        der = load_certificate_der(str(p12_path), "test")
        cert_info = _load_pkcs12(str(p12_path), "test")
        assert der == cert_info.cert_der

    def test_no_password(self, p12_path_no_password: Path) -> None:
        der = load_certificate_der(str(p12_path_no_password), None)
        assert isinstance(der, bytes)
        assert len(der) > 0

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_certificate_der("/nonexistent/cert.p12", None)


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
        config = XAdESSignerConfig(cert_path=str(p12_path_no_password), cert_password=None)
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        assert root.find(f"{{{_DS}}}Signature") is not None

    def test_original_content_preserved(self, p12_path: Path) -> None:
        config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XAdESEPESSigner(config).sign(SAMPLE_XML)
        root = etree.fromstring(result)
        # The original root tag must still be present
        assert "Facturae" in root.tag

    def test_signed_info_references_document_and_signed_properties(self, p12_path: Path) -> None:
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
        with patch.dict(
            "sys.modules",
            {
                "cryptography": None,
                "cryptography.hazmat": None,
                "cryptography.hazmat.primitives": None,
                "cryptography.hazmat.primitives.serialization": None,
                "cryptography.hazmat.primitives.serialization.pkcs12": None,
            },
        ):
            config = XAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
            signer = XAdESEPESSigner(config)
            signer._cert_info = None  # force reload
            with pytest.raises(ImportError, match="cryptography"):
                signer.sign(SAMPLE_XML)


class TestXMLDSigSigner:
    def test_returns_xml_bytes(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        assert isinstance(result, bytes)

    def test_signature_is_last_child_of_root(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        assert root[-1].tag == f"{{{_DS}}}Signature"
        assert root[0].tag.endswith("infNFe")

    def test_no_qualifying_properties(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        assert root.find(f".//{{{_XADES}}}QualifyingProperties") is None

    def test_default_algorithm_is_rsa_sha1(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        sm = root.find(f".//{{{_DS}}}SignatureMethod")
        assert sm is not None
        assert sm.get("Algorithm") == "http://www.w3.org/2000/09/xmldsig#rsa-sha1"

    def test_transforms_contains_enveloped_then_c14n(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        transforms = root.find(f".//{{{_DS}}}Transforms")
        assert transforms is not None
        transform_algs = [t.get("Algorithm") for t in transforms]
        assert transform_algs == [_ENVELOPED_TRANSFORM, _C14N_ALG]

    def test_reference_uri_points_at_infnfe_id(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        ref = root.find(f".//{{{_DS}}}Reference")
        assert ref is not None
        assert ref.get("URI") == ("#NFe35260112345678000199550010000000011000000010")

    def test_signature_value_is_non_empty_base64(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        sv = root.find(f".//{{{_DS}}}SignatureValue")
        assert sv is not None and sv.text
        assert len(base64.b64decode(sv.text)) > 0

    def test_key_info_contains_certificate(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        x509 = root.find(f".//{{{_DS}}}X509Certificate")
        assert x509 is not None and x509.text
        base64.b64decode(x509.text)

    def test_configurable_sha256_algorithm(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(
            cert_path=str(p12_path),
            cert_password="test",
            signature_algorithm=_RSA_SHA256_SIGN_ALG,
            digest_algorithm=_SHA256_DIGEST_ALG,
        )
        result = XMLDSigSigner(config).sign(NFE_XML)
        root = etree.fromstring(result)
        sm = root.find(f".//{{{_DS}}}SignatureMethod")
        dm = root.find(f".//{{{_DS}}}DigestMethod")
        assert sm is not None and sm.get("Algorithm") == _RSA_SHA256_SIGN_ALG
        assert dm is not None and dm.get("Algorithm") == _SHA256_DIGEST_ALG

    def test_missing_signed_element_raises_value_error(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        xml_without_infnfe = b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"/>'
        with pytest.raises(ValueError, match="infNFe"):
            XMLDSigSigner(config).sign(xml_without_infnfe)

    def test_missing_id_attribute_raises_value_error(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        xml_without_id = (
            b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
            b'<infNFe versao="4.00"><ide/></infNFe></NFe>'
        )
        with pytest.raises(ValueError, match="Id"):
            XMLDSigSigner(config).sign(xml_without_id)

    def test_verify_not_implemented(self, p12_path: Path) -> None:
        config = XMLDSigSignerConfig(cert_path=str(p12_path), cert_password="test")
        signer = XMLDSigSigner(config)
        with pytest.raises(NotImplementedError):
            signer.verify(NFE_XML)


FATTURA_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
    versione="FPR12">
  <FatturaElettronicaHeader/>
  <FatturaElettronicaBody/>
</p:FatturaElettronica>
"""


class TestCAdESSigner:
    def test_returns_bytes(self, p12_path: Path) -> None:
        config = CAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = CAdESSigner(config).sign(FATTURA_XML)
        assert isinstance(result, bytes)
        assert len(result) > len(FATTURA_XML)

    def test_output_is_valid_pkcs7_der(self, p12_path: Path) -> None:
        from cryptography.hazmat.primitives.serialization import pkcs7

        config = CAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = CAdESSigner(config).sign(FATTURA_XML)
        certs = pkcs7.load_der_pkcs7_certificates(result)
        assert len(certs) >= 1

    def test_signed_output_wraps_original_document(self, p12_path: Path) -> None:
        config = CAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        result = CAdESSigner(config).sign(FATTURA_XML)
        assert FATTURA_XML in result or b"FatturaElettronica" in result

    def test_no_password_cert(self, p12_path_no_password: Path) -> None:
        config = CAdESSignerConfig(cert_path=str(p12_path_no_password), cert_password=None)
        result = CAdESSigner(config).sign(FATTURA_XML)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_verify_not_implemented(self, p12_path: Path) -> None:
        config = CAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        signer = CAdESSigner(config)
        with pytest.raises(NotImplementedError, match="CAdES"):
            signer.verify(b"dummy")

    def test_cleanup_forces_reload(self, p12_path: Path) -> None:
        config = CAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        signer = CAdESSigner(config)
        signer.sign(FATTURA_XML)
        assert signer._cert_info is not None
        signer.cleanup()
        assert signer._cert_info is None
        result = signer.sign(FATTURA_XML)
        assert len(result) > 0

    def test_sign_is_not_mutating(self, p12_path: Path) -> None:
        config = CAdESSignerConfig(cert_path=str(p12_path), cert_password="test")
        signer = CAdESSigner(config)
        original = FATTURA_XML[:]
        signer.sign(FATTURA_XML)
        assert FATTURA_XML == original


# ---------------------------------------------------------------------------
# MX — Sello Digital
#
# The fixtures below are synthetic (not SAT's actual cadena original
# stylesheet — that file is copyrighted SAT material that lives only in
# mcp-cfdi-mx/specs/, exercised by that package's own tests). They mimic the
# same structural pattern confirmed against the supplied Anexo 20 bundle:
# a "Requerido" helper in an included utility stylesheet, and one additional
# include that a document referencing an "extra" complemento would need.
# ---------------------------------------------------------------------------


def _generate_test_csd(cert_path: Path, key_path: Path, password: bytes = b"test") -> None:
    """Write a self-signed DER cert + encrypted PKCS#8 DER key (MX CSD shape)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CSD")])
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
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.DER))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password),
        )
    )


_TEST_UTILERIAS_XSLT = b"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template name="Requerido">
    <xsl:param name="valor"/>|<xsl:value-of select="normalize-space(string($valor))"/>
  </xsl:template>
</xsl:stylesheet>
"""

_TEST_CADENA_ORIGINAL_XSLT_TEMPLATE = b"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:include href="http://example.test/utilerias.xslt"/>
  <xsl:include href="http://www.sat.gob.mx/sitio_internet/cfd/unused/unused_complemento.xslt"/>
  <xsl:output method="text" encoding="UTF-8"/>
  <xsl:template match="/Comprobante">|<xsl:call-template name="Requerido">
      <xsl:with-param name="valor" select="./@NoCertificado"/>
    </xsl:call-template>|<xsl:call-template name="Requerido">
      <xsl:with-param name="valor" select="./@Total"/>
    </xsl:call-template>||</xsl:template>
</xsl:stylesheet>
"""

MX_SAMPLE_XML = b'<?xml version="1.0" encoding="UTF-8"?><Comprobante Total="100.00"/>'


@pytest.fixture()
def csd_paths(tmp_path: Path) -> tuple[Path, Path]:
    cert_path = tmp_path / "csd.cer"
    key_path = tmp_path / "csd.key"
    _generate_test_csd(cert_path, key_path, password=b"test")
    return cert_path, key_path


@pytest.fixture()
def cadena_original_xslt_path(tmp_path: Path) -> Path:
    utilerias_path = tmp_path / "utilerias.xslt"
    utilerias_path.write_bytes(_TEST_UTILERIAS_XSLT)
    entry_path = tmp_path / "cadenaoriginal_test.xslt"
    entry_path.write_bytes(_TEST_CADENA_ORIGINAL_XSLT_TEMPLATE)
    return entry_path


def _sello_config(
    csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
) -> SelloDigitalSignerConfig:
    cert_path, key_path = csd_paths
    return SelloDigitalSignerConfig(
        cert_path=str(cert_path),
        key_path=str(key_path),
        key_password="test",
        no_certificado="30001000000500003416",
        cadena_original_xslt_path=str(cadena_original_xslt_path),
        xslt_include_paths={
            "http://example.test/utilerias.xslt": str(
                cadena_original_xslt_path.parent / "utilerias.xslt"
            ),
        },
    )


class TestSelloDigitalSigner:
    def test_sign_populates_attributes(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        signer = SelloDigitalSigner(config)
        result = signer.sign(MX_SAMPLE_XML)

        root = etree.fromstring(result)
        assert root.get("NoCertificado") == "30001000000500003416"
        assert root.get("Certificado")
        assert root.get("Sello")
        base64.b64decode(root.get("Certificado"))
        base64.b64decode(root.get("Sello"))

    def test_sign_verify_roundtrip(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        signer = SelloDigitalSigner(config)
        signed = signer.sign(MX_SAMPLE_XML)
        assert SelloDigitalSigner(config).verify(signed) is True

    def test_verify_rejects_tampered_document(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        signer = SelloDigitalSigner(config)
        signed = signer.sign(MX_SAMPLE_XML)
        tampered = signed.replace(b'Total="100.00"', b'Total="999.00"')
        assert SelloDigitalSigner(config).verify(tampered) is False

    def test_unresolved_include_is_stubbed_by_default(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        # The config in _sello_config only maps utilerias.xslt; the second
        # include (unused_complemento.xslt) is never mapped and must still
        # compile via the stub resolver since sign() never invokes it.
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        result = SelloDigitalSigner(config).sign(MX_SAMPLE_XML)
        assert etree.fromstring(result).get("Sello")

    def test_unresolved_include_raises_when_stubbing_disabled(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        config.stub_unresolved_includes = False
        with pytest.raises(ValueError, match="Unresolved SAT cadena original include"):
            SelloDigitalSigner(config).sign(MX_SAMPLE_XML)

    def test_no_certificado_not_derived_from_cert(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        # NoCertificado must come from config, not be silently derived from
        # the certificate's ASN.1 serial number (no confirmed algorithm).
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        config.no_certificado = "99999999999999999999"
        result = SelloDigitalSigner(config).sign(MX_SAMPLE_XML)
        assert etree.fromstring(result).get("NoCertificado") == "99999999999999999999"

    def test_missing_root_element_raises(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        with pytest.raises(ValueError, match="No <Comprobante> element"):
            SelloDigitalSigner(config).sign(b"<Otro/>")

    def test_verify_missing_sello_raises(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        with pytest.raises(ValueError, match="no 'Sello' attribute"):
            SelloDigitalSigner(config).verify(MX_SAMPLE_XML)

    def test_cleanup_forces_reload(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        signer = SelloDigitalSigner(config)
        signer.sign(MX_SAMPLE_XML)
        assert signer._csd_info is not None
        signer.cleanup()
        assert signer._csd_info is None
        result = signer.sign(MX_SAMPLE_XML)
        assert len(result) > 0

    def test_sign_is_not_mutating(
        self, csd_paths: tuple[Path, Path], cadena_original_xslt_path: Path
    ) -> None:
        config = _sello_config(csd_paths, cadena_original_xslt_path)
        signer = SelloDigitalSigner(config)
        original = MX_SAMPLE_XML[:]
        signer.sign(MX_SAMPLE_XML)
        assert MX_SAMPLE_XML == original
