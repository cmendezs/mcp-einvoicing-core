"""Tests for Peppol PKI trust-store validation (CORE-PEPPOL-TRUST-1)."""

from __future__ import annotations

import base64
import datetime
import hashlib
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from mcp_einvoicing_core.peppol import PeppolEnvironment
from mcp_einvoicing_core.peppol.trust import (
    PeppolPKINotConfiguredError,
    PeppolTrustStore,
    check_revocation,
    validate_certificate_chain,
    verify_smp_signature,
)

# ---------------------------------------------------------------------------
# Mini test PKI: self-signed root CA + leaf signed by it
# ---------------------------------------------------------------------------


def _build_root_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    now = datetime.datetime.now(datetime.UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Peppol Root CA")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _build_leaf(
    root_key: rsa.RSAPrivateKey, root_cert: x509.Certificate
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    now = datetime.datetime.now(datetime.UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test AP Leaf")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(root_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(root_key, hashes.SHA256())
    )
    return key, cert


@pytest.fixture()
def root_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    return _build_root_ca()


@pytest.fixture()
def leaf(root_ca: tuple[rsa.RSAPrivateKey, x509.Certificate]) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    root_key, root_cert = root_ca
    return _build_leaf(root_key, root_cert)


@pytest.fixture()
def pki_dir(
    tmp_path: Path,
    root_ca: tuple[rsa.RSAPrivateKey, x509.Certificate],
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    _, root_cert = root_ca
    (tmp_path / "test").mkdir()
    (tmp_path / "prod").mkdir()
    (tmp_path / "test" / "root.pem").write_bytes(
        root_cert.public_bytes(serialization.Encoding.PEM)
    )
    monkeypatch.setenv("EINVOICING_PEPPOL_PKI_DIR", str(tmp_path))
    return tmp_path


class TestPeppolTrustStore:
    def test_unconfigured_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_PEPPOL_PKI_DIR", raising=False)
        store = PeppolTrustStore(PeppolEnvironment.TEST)
        with pytest.raises(PeppolPKINotConfiguredError):
            store.load_root_certs()

    def test_missing_subdir_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EINVOICING_PEPPOL_PKI_DIR", str(tmp_path))
        store = PeppolTrustStore(PeppolEnvironment.PRODUCTION)
        with pytest.raises(PeppolPKINotConfiguredError):
            store.load_root_certs()

    def test_loads_configured_root(self, pki_dir: Path) -> None:
        store = PeppolTrustStore(PeppolEnvironment.TEST)
        certs = store.load_root_certs()
        assert len(certs) == 1


class TestValidateCertificateChain:
    def test_unconfigured_reports_status(
        self,
        leaf: tuple[rsa.RSAPrivateKey, x509.Certificate],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("EINVOICING_PEPPOL_PKI_DIR", raising=False)
        _, leaf_cert = leaf
        result = validate_certificate_chain(
            leaf_cert.public_bytes(serialization.Encoding.PEM), PeppolEnvironment.TEST
        )
        assert result["trust_anchors_configured"] is False
        assert result["status"] == "trust-anchors-not-configured"

    def test_valid_chain(
        self, leaf: tuple[rsa.RSAPrivateKey, x509.Certificate], pki_dir: Path
    ) -> None:
        _, leaf_cert = leaf
        result = validate_certificate_chain(
            leaf_cert.public_bytes(serialization.Encoding.PEM), PeppolEnvironment.TEST
        )
        assert result["trust_anchors_configured"] is True
        assert result["valid"] is True
        assert result["status"] == "valid"

    def test_untrusted_issuer_rejected(self, pki_dir: Path) -> None:
        other_root_key, other_root_cert = _build_root_ca()
        _, rogue_leaf_cert = _build_leaf(other_root_key, other_root_cert)
        result = validate_certificate_chain(
            rogue_leaf_cert.public_bytes(serialization.Encoding.PEM), PeppolEnvironment.TEST
        )
        assert result["trust_anchors_configured"] is True
        assert result["valid"] is False
        assert result["status"] == "invalid"

    def test_prod_env_uses_prod_subdir_not_test(
        self, leaf: tuple[rsa.RSAPrivateKey, x509.Certificate], pki_dir: Path
    ) -> None:
        # pki_dir fixture only populates test/, not prod/
        _, leaf_cert = leaf
        result = validate_certificate_chain(
            leaf_cert.public_bytes(serialization.Encoding.PEM), PeppolEnvironment.PRODUCTION
        )
        assert result["trust_anchors_configured"] is False


class TestCheckRevocation:
    async def test_no_aia_or_cdp_not_checked(
        self, leaf: tuple[rsa.RSAPrivateKey, x509.Certificate], root_ca
    ) -> None:
        _, leaf_cert = leaf
        _, root_cert = root_ca
        result = await check_revocation(
            leaf_cert.public_bytes(serialization.Encoding.PEM),
            root_cert.public_bytes(serialization.Encoding.PEM),
        )
        assert result.checked is False
        assert result.revoked is None

    async def test_ocsp_good_response(self, root_ca, httpx_mock) -> None:
        root_key, root_cert = root_ca
        leaf_key, leaf_cert = _build_ocsp_leaf(root_key, root_cert)

        from cryptography.x509 import ocsp as ocsp_mod

        builder = ocsp_mod.OCSPResponseBuilder()
        builder = builder.add_response(
            cert=leaf_cert,
            issuer=root_cert,
            algorithm=hashes.SHA1(),
            cert_status=ocsp_mod.OCSPCertStatus.GOOD,
            this_update=datetime.datetime.now(datetime.UTC),
            next_update=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1),
            revocation_time=None,
            revocation_reason=None,
        ).responder_id(ocsp_mod.OCSPResponderEncoding.HASH, root_cert)
        response = builder.sign(root_key, hashes.SHA256())

        httpx_mock.add_response(
            content=response.public_bytes(serialization.Encoding.DER),
            headers={"Content-Type": "application/ocsp-response"},
        )

        result = await check_revocation(
            leaf_cert.public_bytes(serialization.Encoding.PEM),
            root_cert.public_bytes(serialization.Encoding.PEM),
        )
        assert result.checked is True
        assert result.revoked is False
        assert result.method == "ocsp"

    async def test_ocsp_revoked_response(self, root_ca, httpx_mock) -> None:
        root_key, root_cert = root_ca
        leaf_key, leaf_cert = _build_ocsp_leaf(root_key, root_cert)

        from cryptography.x509 import ocsp as ocsp_mod

        builder = ocsp_mod.OCSPResponseBuilder()
        builder = builder.add_response(
            cert=leaf_cert,
            issuer=root_cert,
            algorithm=hashes.SHA1(),
            cert_status=ocsp_mod.OCSPCertStatus.REVOKED,
            this_update=datetime.datetime.now(datetime.UTC),
            next_update=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1),
            revocation_time=datetime.datetime.now(datetime.UTC),
            revocation_reason=x509.ReasonFlags.key_compromise,
        ).responder_id(ocsp_mod.OCSPResponderEncoding.HASH, root_cert)
        response = builder.sign(root_key, hashes.SHA256())

        httpx_mock.add_response(
            content=response.public_bytes(serialization.Encoding.DER),
        )

        result = await check_revocation(
            leaf_cert.public_bytes(serialization.Encoding.PEM),
            root_cert.public_bytes(serialization.Encoding.PEM),
        )
        assert result.checked is True
        assert result.revoked is True
        assert result.method == "ocsp"


def _build_ocsp_leaf(
    root_key: rsa.RSAPrivateKey, root_cert: x509.Certificate
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    now = datetime.datetime.now(datetime.UTC)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test AP Leaf OCSP")])
    aia = x509.AuthorityInformationAccess(
        [
            x509.AccessDescription(
                x509.AuthorityInformationAccessOID.OCSP,
                x509.UniformResourceIdentifier("http://ocsp.test.example/"),
            )
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(root_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(aia, critical=False)
        .sign(root_key, hashes.SHA256())
    )
    return key, cert


# ---------------------------------------------------------------------------
# verify_smp_signature — hand-built enveloped XML-DSig fixture
# ---------------------------------------------------------------------------

_DS_NS = "http://www.w3.org/2000/09/xmldsig#"
_SMD_NS = "http://busdox.org/serviceMetadata/publishing/1.0/"


def _qn(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _build_signed_service_metadata(
    private_key: rsa.RSAPrivateKey, cert_der: bytes
) -> bytes:
    root = etree.Element(_qn(_SMD_NS, "SignedServiceMetadata"), nsmap={"smd": _SMD_NS})
    sm = etree.SubElement(root, _qn(_SMD_NS, "ServiceMetadata"))
    si = etree.SubElement(sm, _qn(_SMD_NS, "ServiceInformation"))
    etree.SubElement(si, _qn(_SMD_NS, "ParticipantIdentifier")).text = "0208:0123456789"

    doc_c14n = etree.tostring(root, method="c14n", exclusive=False, with_comments=False)
    doc_digest = base64.b64encode(hashlib.sha256(doc_c14n).digest()).decode()

    nsmap = {"ds": _DS_NS}
    signature = etree.Element(_qn(_DS_NS, "Signature"), nsmap=nsmap)
    signed_info = etree.SubElement(signature, _qn(_DS_NS, "SignedInfo"))
    cm = etree.SubElement(signed_info, _qn(_DS_NS, "CanonicalizationMethod"))
    cm.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    sm_el = etree.SubElement(signed_info, _qn(_DS_NS, "SignatureMethod"))
    sm_el.set("Algorithm", "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256")
    ref = etree.SubElement(signed_info, _qn(_DS_NS, "Reference"))
    ref.set("URI", "")
    transforms = etree.SubElement(ref, _qn(_DS_NS, "Transforms"))
    etree.SubElement(transforms, _qn(_DS_NS, "Transform")).set(
        "Algorithm", "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
    )
    dm = etree.SubElement(ref, _qn(_DS_NS, "DigestMethod"))
    dm.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
    etree.SubElement(ref, _qn(_DS_NS, "DigestValue")).text = doc_digest

    # Attach the (still-unsigned) Signature to the document *before*
    # canonicalizing SignedInfo for signing: plain (non-exclusive) C14N of an
    # element considers ancestor namespace declarations in scope (here,
    # root's xmlns:smd), so SignedInfo must be canonicalized in the same
    # document context a verifier will later re-extract it from — matching
    # mcp_einvoicing_core.peppol.trust.verify_smp_signature's recomputation.
    root.append(signature)

    signed_info_c14n = etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False)
    signature_bytes = private_key.sign(signed_info_c14n, padding.PKCS1v15(), hashes.SHA256())
    sv = etree.SubElement(signature, _qn(_DS_NS, "SignatureValue"))
    sv.text = base64.b64encode(signature_bytes).decode()

    key_info = etree.SubElement(signature, _qn(_DS_NS, "KeyInfo"))
    x509_data = etree.SubElement(key_info, _qn(_DS_NS, "X509Data"))
    etree.SubElement(x509_data, _qn(_DS_NS, "X509Certificate")).text = (
        base64.b64encode(cert_der).decode()
    )

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


class TestVerifySmpSignature:
    def test_valid_signature(self, leaf: tuple[rsa.RSAPrivateKey, x509.Certificate]) -> None:
        key, cert = leaf
        cert_der = cert.public_bytes(serialization.Encoding.DER)
        signed_xml = _build_signed_service_metadata(key, cert_der)

        result = verify_smp_signature(signed_xml)
        assert result["signature_valid"] is True
        assert result["error"] is None

    def test_tampered_content_fails(
        self, leaf: tuple[rsa.RSAPrivateKey, x509.Certificate]
    ) -> None:
        key, cert = leaf
        cert_der = cert.public_bytes(serialization.Encoding.DER)
        signed_xml = _build_signed_service_metadata(key, cert_der)

        tampered = signed_xml.replace(b"0208:0123456789", b"0208:9999999999")
        result = verify_smp_signature(tampered)
        assert result["signature_valid"] is False

    def test_no_signature_element(self) -> None:
        result = verify_smp_signature(b"<root><child/></root>")
        assert result["signature_valid"] is False
        assert "No ds:Signature" in result["error"]

    def test_with_environment_attaches_chain_result(
        self, leaf: tuple[rsa.RSAPrivateKey, x509.Certificate], pki_dir: Path
    ) -> None:
        key, cert = leaf
        cert_der = cert.public_bytes(serialization.Encoding.DER)
        signed_xml = _build_signed_service_metadata(key, cert_der)

        result = verify_smp_signature(signed_xml, environment=PeppolEnvironment.TEST)
        assert result["signature_valid"] is True
        assert result["chain"]["valid"] is True
