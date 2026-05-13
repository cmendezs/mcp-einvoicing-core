"""XAdES-EPES digital signature for e-invoicing XML documents.

Implements XMLDSig enveloped signature with XAdES-EPES qualifying properties
(signing time, signer certificate digest, optional signature policy identifier).

Requires the [xml-sign] optional extra:
    pip install 'mcp-einvoicing-core[xml-sign]'

Used by:
  ES — Facturae 3.2.2 (Orden EHA/962/2007 signature policy)
  ES — TicketBAI (per-province policy OIDs: Álava, Gipuzkoa, Bizkaia)
  [NEED: FR Chorus Pro CAdES attachment path — confirm whether XAdES applies]
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from lxml import etree

# XML namespace constants
_DS = "http://www.w3.org/2000/09/xmldsig#"
_XADES = "http://uri.etsi.org/01903/v1.3.2#"
_DS_PREFIX = "ds"
_XADES_PREFIX = "xades"

# Algorithm URIs
_C14N_ALG = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
_SIGN_ALG = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
_DIGEST_ALG = "http://www.w3.org/2001/04/xmlenc#sha256"
_ENVELOPED_TRANSFORM = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
_SIGNED_PROPS_TYPE = "http://uri.etsi.org/01903#SignedProperties"


@dataclass
class XAdESSignerConfig:
    """Configuration for XAdES-EPES signing.

    Attributes:
        cert_path: Path to the PKCS#12 (.p12 / .pfx) certificate file.
        cert_password: Passphrase for the PKCS#12 file, or ``None`` if
            unprotected.
        signature_policy_id: URI of the signature policy (ETSI TS 101 733).
            Required for EPES; ``None`` produces an implied-policy XAdES-BES.
        signature_policy_hash: Base64-encoded SHA-256 digest of the policy
            document. Required when *signature_policy_id* is set.
        signature_policy_hash_alg: Algorithm URI for the policy hash.
            Defaults to SHA-256.
        claimed_role: Optional signer role (e.g. ``"supplier"``).
    """

    cert_path: str
    cert_password: Optional[str] = None
    signature_policy_id: Optional[str] = None
    signature_policy_hash: Optional[str] = None
    signature_policy_hash_alg: str = _DIGEST_ALG
    claimed_role: Optional[str] = None


@dataclass
class _CertInfo:
    """Parsed certificate material needed for signature construction."""

    cert_der: bytes
    cert_sha256: bytes
    issuer_dn: str
    serial_number: int
    private_key: object = field(repr=False)


def _load_pkcs12(cert_path: str, cert_password: Optional[str]) -> _CertInfo:
    """Load a PKCS#12 file and return the signing material."""
    try:
        from cryptography.hazmat.primitives.serialization.pkcs12 import (  # noqa: PLC0415
            load_pkcs12,
        )
        from cryptography.hazmat.primitives.serialization import Encoding  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "cryptography>=42.0.0 is required for XAdES signing. "
            "Install: pip install 'mcp-einvoicing-core[xml-sign]'"
        ) from exc

    with open(cert_path, "rb") as fh:
        raw = fh.read()

    password = cert_password.encode() if cert_password else None
    p12 = load_pkcs12(raw, password)

    if p12.cert is None:
        raise ValueError(f"No certificate found in PKCS#12 file: {cert_path}")
    if p12.key is None:
        raise ValueError(f"No private key found in PKCS#12 file: {cert_path}")

    cert = p12.cert.certificate
    cert_der = cert.public_bytes(Encoding.DER)
    cert_sha256 = hashlib.sha256(cert_der).digest()

    # Build issuer DN in RFC 4514 style (reversed RDN order for XMLDSig)
    issuer_dn = cert.issuer.rfc4514_string()

    return _CertInfo(
        cert_der=cert_der,
        cert_sha256=cert_sha256,
        issuer_dn=issuer_dn,
        serial_number=cert.serial_number,
        private_key=p12.key,
    )


def _qn(ns: str, local: str) -> str:
    """Return a Clark-notation qualified name ``{ns}local``."""
    return f"{{{ns}}}{local}"


def _make_element(
    ns: str,
    prefix: str,
    local: str,
    nsmap: Optional[dict[str, str]] = None,
    text: Optional[str] = None,
    attrib: Optional[dict[str, str]] = None,
) -> etree._Element:
    """Create an lxml element with the given namespace and optional content."""
    full_nsmap = {prefix: ns}
    if nsmap:
        full_nsmap.update(nsmap)
    elem = etree.Element(_qn(ns, local), nsmap=full_nsmap)
    if attrib:
        for k, v in attrib.items():
            elem.set(k, v)
    if text is not None:
        elem.text = text
    return elem


def _c14n(element: etree._Element) -> bytes:
    """Return the canonical XML 1.0 serialisation of *element*."""
    return etree.tostring(element, method="c14n")


def _sha256_b64(data: bytes) -> str:
    """Return base64-encoded SHA-256 digest of *data*."""
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def _build_signed_properties(
    sp_id: str,
    signing_time: str,
    cert_info: _CertInfo,
    config: XAdESSignerConfig,
) -> etree._Element:
    """Build the xades:SignedProperties element."""
    nsmap = {_DS_PREFIX: _DS, _XADES_PREFIX: _XADES}
    sp = etree.Element(_qn(_XADES, "SignedProperties"), nsmap=nsmap)
    sp.set("Id", sp_id)

    ssp = etree.SubElement(sp, _qn(_XADES, "SignedSignatureProperties"))

    # SigningTime
    etree.SubElement(ssp, _qn(_XADES, "SigningTime")).text = signing_time

    # SigningCertificateV2
    sc = etree.SubElement(ssp, _qn(_XADES, "SigningCertificateV2"))
    cert_elem = etree.SubElement(sc, _qn(_XADES, "Cert"))
    cd = etree.SubElement(cert_elem, _qn(_XADES, "CertDigest"))
    dm = etree.SubElement(cd, _qn(_DS, "DigestMethod"))
    dm.set("Algorithm", _DIGEST_ALG)
    etree.SubElement(cd, _qn(_DS, "DigestValue")).text = base64.b64encode(
        cert_info.cert_sha256
    ).decode()
    isv = etree.SubElement(cert_elem, _qn(_XADES, "IssuerSerialV2"))
    # IssuerSerialV2 encodes the ASN.1 IssuerSerial as base64 DER; for
    # interoperability we include the text form and the serial number.
    # [NEED: verify exact encoding for Facturae/TicketBAI policy validation]
    isv.text = base64.b64encode(
        f"{cert_info.issuer_dn},{cert_info.serial_number}".encode()
    ).decode()

    # SignaturePolicyIdentifier (EPES only)
    if config.signature_policy_id:
        spi = etree.SubElement(ssp, _qn(_XADES, "SignaturePolicyIdentifier"))
        spid = etree.SubElement(spi, _qn(_XADES, "SignaturePolicyId"))
        sig_pol_id = etree.SubElement(spid, _qn(_XADES, "SigPolicyId"))
        etree.SubElement(sig_pol_id, _qn(_XADES, "Identifier")).text = (
            config.signature_policy_id
        )
        if config.signature_policy_hash:
            sph = etree.SubElement(spid, _qn(_XADES, "SigPolicyHash"))
            hash_dm = etree.SubElement(sph, _qn(_DS, "DigestMethod"))
            hash_dm.set("Algorithm", config.signature_policy_hash_alg)
            etree.SubElement(sph, _qn(_DS, "DigestValue")).text = (
                config.signature_policy_hash
            )

    # ClaimedRole (optional)
    if config.claimed_role:
        sr = etree.SubElement(ssp, _qn(_XADES, "SignerRole"))
        cr = etree.SubElement(sr, _qn(_XADES, "ClaimedRoles"))
        etree.SubElement(cr, _qn(_XADES, "ClaimedRole")).text = config.claimed_role

    return sp


def _build_signed_info(
    doc_digest: str,
    sp_ref_id: str,
    sp_digest: str,
) -> etree._Element:
    """Build the ds:SignedInfo element with two References."""
    nsmap = {_DS_PREFIX: _DS}
    si = etree.Element(_qn(_DS, "SignedInfo"), nsmap=nsmap)

    cm = etree.SubElement(si, _qn(_DS, "CanonicalizationMethod"))
    cm.set("Algorithm", _C14N_ALG)

    sm = etree.SubElement(si, _qn(_DS, "SignatureMethod"))
    sm.set("Algorithm", _SIGN_ALG)

    # Reference 1: the document itself (enveloped transform)
    ref1 = etree.SubElement(si, _qn(_DS, "Reference"))
    ref1.set("URI", "")
    transforms = etree.SubElement(ref1, _qn(_DS, "Transforms"))
    t = etree.SubElement(transforms, _qn(_DS, "Transform"))
    t.set("Algorithm", _ENVELOPED_TRANSFORM)
    dm1 = etree.SubElement(ref1, _qn(_DS, "DigestMethod"))
    dm1.set("Algorithm", _DIGEST_ALG)
    etree.SubElement(ref1, _qn(_DS, "DigestValue")).text = doc_digest

    # Reference 2: the XAdES SignedProperties
    ref2 = etree.SubElement(si, _qn(_DS, "Reference"))
    ref2.set("Id", sp_ref_id)
    ref2.set("Type", _SIGNED_PROPS_TYPE)
    ref2.set("URI", f"#{sp_ref_id.replace('Ref-', '')}")
    dm2 = etree.SubElement(ref2, _qn(_DS, "DigestMethod"))
    dm2.set("Algorithm", _DIGEST_ALG)
    etree.SubElement(ref2, _qn(_DS, "DigestValue")).text = sp_digest

    return si


def _build_key_info(cert_info: _CertInfo) -> etree._Element:
    """Build the ds:KeyInfo element with the signer certificate."""
    nsmap = {_DS_PREFIX: _DS}
    ki = etree.Element(_qn(_DS, "KeyInfo"), nsmap=nsmap)
    x509_data = etree.SubElement(ki, _qn(_DS, "X509Data"))
    etree.SubElement(ki, _qn(_DS, "X509Data"))  # placeholder cleared below
    ki.remove(ki[-1])  # remove duplicate
    etree.SubElement(x509_data, _qn(_DS, "X509Certificate")).text = (
        base64.b64encode(cert_info.cert_der).decode()
    )
    return ki


def _sign_bytes(private_key: object, data: bytes) -> bytes:
    """RSA-SHA256 sign *data* with *private_key*."""
    try:
        from cryptography.hazmat.primitives import hashes  # noqa: PLC0415
        from cryptography.hazmat.primitives.asymmetric import padding  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "cryptography>=42.0.0 is required for XAdES signing."
        ) from exc
    return private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr]


class XAdESEPESSigner:
    """Apply an XAdES-EPES enveloped signature to an XML document.

    The signer adds a ``ds:Signature`` element as the last child of the root
    element. The document digest is computed over the original XML bytes
    (before the signature is injected) so the ``enveloped-signature`` transform
    in the ``ds:Reference`` element correctly describes what was signed.

    Example::

        config = XAdESSignerConfig(
            cert_path="/path/to/cert.p12",
            cert_password="secret",
            signature_policy_id="http://www.facturae.es/politica_de_firma/...",
            signature_policy_hash="<base64-sha256-of-policy-pdf>",
        )
        signer = XAdESEPESSigner(config)
        signed_xml = signer.sign(original_xml_bytes)
    """

    def __init__(self, config: XAdESSignerConfig) -> None:
        self._config = config
        self._cert_info: Optional[_CertInfo] = None

    def _get_cert_info(self) -> _CertInfo:
        if self._cert_info is None:
            self._cert_info = _load_pkcs12(
                self._config.cert_path, self._config.cert_password
            )
        return self._cert_info

    def sign(self, xml_bytes: bytes) -> bytes:
        """Return *xml_bytes* with an embedded XAdES-EPES signature.

        Args:
            xml_bytes: Well-formed XML document to sign.

        Returns:
            UTF-8 XML document with ``ds:Signature`` appended to the root
            element.

        Raises:
            ImportError: If ``cryptography`` is not installed.
            ValueError: If the PKCS#12 file contains no certificate or key.
        """
        cert_info = self._get_cert_info()

        # Unique IDs for this signature instance
        sig_uuid = uuid.uuid4().hex[:16]
        sig_id = f"Signature-{sig_uuid}"
        sp_id = f"SignedProperties-{sig_uuid}"
        sp_ref_id = f"Ref-{sp_id}"

        signing_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Step 1: parse the document and compute its C14N digest
        # (before injecting the signature — this is what the enveloped-
        # signature transform on the final document will reproduce)
        root = etree.fromstring(xml_bytes)
        doc_c14n = _c14n(root)
        doc_digest = _sha256_b64(doc_c14n)

        # Step 2: build SignedProperties and compute its C14N digest
        sp_elem = _build_signed_properties(sp_id, signing_time, cert_info, self._config)
        sp_digest = _sha256_b64(_c14n(sp_elem))

        # Step 3: build SignedInfo and sign its C14N
        si_elem = _build_signed_info(doc_digest, sp_ref_id, sp_digest)
        si_c14n = _c14n(si_elem)
        sig_value_bytes = _sign_bytes(cert_info.private_key, si_c14n)
        sig_value_b64 = base64.b64encode(sig_value_bytes).decode()

        # Step 4: assemble the ds:Signature element
        nsmap = {_DS_PREFIX: _DS, _XADES_PREFIX: _XADES}
        sig_elem = etree.Element(_qn(_DS, "Signature"), nsmap=nsmap)
        sig_elem.set("Id", sig_id)

        sig_elem.append(si_elem)

        sv = etree.SubElement(sig_elem, _qn(_DS, "SignatureValue"))
        sv.set("Id", f"SignatureValue-{sig_uuid}")
        sv.text = sig_value_b64

        sig_elem.append(_build_key_info(cert_info))

        obj_elem = etree.SubElement(sig_elem, _qn(_DS, "Object"))
        qp = etree.SubElement(obj_elem, _qn(_XADES, "QualifyingProperties"))
        qp.set("Target", f"#{sig_id}")
        qp.append(sp_elem)

        # Step 5: append the signature to the document root
        root.append(sig_elem)

        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
