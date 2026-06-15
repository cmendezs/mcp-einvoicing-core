"""Digital signature ABCs and XAdES-EPES / XML-DSig implementations for e-invoicing XML.

Public API
----------
BaseDocumentSigner
    Abstract base class for all document-level signers. Extend this for any
    new signing standard (CAdES, PKCS#7, ZATCA stamp, Sello Digital …).

XAdESSignerConfig, XAdESEPESSigner
    Concrete XAdES-EPES implementation for ES Facturae and TicketBAI.
    Requires the [xml-sign] optional extra:
        pip install 'mcp-einvoicing-core[xml-sign]'

XMLDSigSignerConfig, XMLDSigSigner
    Plain enveloped XML-DSig implementation (not XAdES) for BR NF-e/NFC-e.
    Requires the [xml-sign] optional extra.

Used by:
  ES — Facturae 3.2.2 (Orden EHA/962/2007 signature policy)
  ES — TicketBAI (per-province policy OIDs: Álava, Gipuzkoa, Bizkaia)
  BR — NF-e/NFC-e (enveloped XML-DSig over infNFe, RSA-SHA1 per MOC 7.0
       Table 4-2; CT-e/NFS-e expected to reuse the same signer)
  [NEED: FR Chorus Pro CAdES attachment path — confirm whether XAdES applies]
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from lxml import etree

from mcp_einvoicing_core.xml_utils import safe_fromstring


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseDocumentSigner(ABC):
    """Abstract base class for all document-level signers.

    Lifecycle contract for all concrete implementations:

    1. ``load_credentials()`` — load private key + certificate into memory
       (PKCS#12, HSM slot, environment-supplied key). Called automatically
       by ``sign()`` on first use; may also be called explicitly to pre-warm.
    2. ``sign(document)`` — apply the algorithm-specific signature and return
       the signed document.
    3. ``verify(signed_document)`` — verify that the embedded signature is
       cryptographically valid.

    Concrete implementations cover different signing standards:

    - ``XAdESEPESSigner`` — XAdES-EPES enveloped XML signature
      (ES Facturae / TicketBAI; ETSI TS 101 903)
    - ``XMLDSigSigner`` — plain enveloped XML-DSig, no XAdES qualifying
      properties (BR NF-e/NFC-e; CT-e/NFS-e expected to reuse)
    - [Future] CAdES — CAdES attached/detached for FR Chorus Pro PDF/A-3
    - [Future] ZATCASigner — ZATCA cryptographic stamp (HSM-backed, SA Phase 2)
    - [Future] SelloDigitalSigner — MX CFDI Sello Digital (RSA-SHA256 + base64)

    All implementations must satisfy two invariants:
    1. ``sign(document)`` is idempotent for the same *document* + credential pair.
    2. ``sign(document)`` never mutates *document* in place.
    """

    @abstractmethod
    def load_credentials(self) -> None:
        """Load signing credentials into memory.

        Implementations load a PKCS#12 file, open an HSM slot, or read an
        environment-supplied key. After this method returns the instance must
        hold the private key and certificate material needed by ``sign()``.

        Called automatically by ``sign()`` on first use. May also be called
        explicitly to validate credentials at startup before the first document
        is signed.

        Raises:
            ImportError: If a required cryptographic library is not installed.
            ValueError: If the credential store is missing, corrupt, or
                incompatible with this signer.
        """

    @abstractmethod
    def sign(self, document: bytes) -> bytes:
        """Sign *document* and return the signed result.

        Implementations must call ``load_credentials()`` if credentials have
        not been loaded yet (lazy initialisation is acceptable).

        Args:
            document: Raw document bytes to sign. The format (XML, PDF, JSON)
                is determined by the concrete signer.

        Returns:
            Signed document bytes. The embedding strategy (enveloped, detached,
            attached) and output format are implementation-specific.

        Raises:
            ImportError: If a required signing library is not installed.
            ValueError: If signing material is missing, invalid, or incompatible
                with the document format.
        """

    @abstractmethod
    def verify(self, signed_document: bytes) -> bool:
        """Return True if the signature embedded in *signed_document* is valid.

        Args:
            signed_document: Signed document bytes in the same format returned
                by ``sign()``.

        Returns:
            True if the signature is cryptographically valid. Implementations
            may additionally check certificate trust chains and policy OIDs
            where feasible; document any limitations in the concrete class.

        Raises:
            ImportError: If a required verification library is not installed.
            ValueError: If the document format is unrecognised or malformed.
        """

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

# Additional algorithm URIs used by XMLDSigSigner (configurable; NF-e
# historically uses RSA-SHA1, confirmed against MOC 7.0 Table 4-2)
_RSA_SHA1_SIGN_ALG = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
_RSA_SHA256_SIGN_ALG = _SIGN_ALG
_SHA1_DIGEST_ALG = "http://www.w3.org/2000/09/xmldsig#sha1"
_SHA256_DIGEST_ALG = _DIGEST_ALG

# Maps a SignatureMethod algorithm URI to the `cryptography` hash-algorithm
# name expected by _sign_bytes().
_SIGN_ALG_HASH_NAMES = {
    _RSA_SHA1_SIGN_ALG: "sha1",
    _RSA_SHA256_SIGN_ALG: "sha256",
}

# Maps a DigestMethod algorithm URI to the hashlib algorithm name expected
# by _digest_b64().
_DIGEST_ALG_HASH_NAMES = {
    _SHA1_DIGEST_ALG: "sha1",
    _SHA256_DIGEST_ALG: "sha256",
}


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


def _digest_b64(data: bytes, digest_algorithm: str) -> str:
    """Return the base64-encoded digest of *data* using *digest_algorithm*.

    Args:
        data: Bytes to digest.
        digest_algorithm: A ``ds:DigestMethod`` algorithm URI. Recognised
            values are SHA-1 and SHA-256; unrecognised URIs fall back to
            SHA-256.
    """
    hash_name = _DIGEST_ALG_HASH_NAMES.get(digest_algorithm, "sha256")
    return base64.b64encode(hashlib.new(hash_name, data).digest()).decode()


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


def _sign_bytes(private_key: object, data: bytes, hash_algorithm: str = "sha256") -> bytes:
    """RSA-sign *data* with *private_key* using PKCS#1 v1.5 padding.

    Args:
        private_key: An RSA private key object from ``cryptography``.
        data: Bytes to sign (typically the C14N of a ``ds:SignedInfo``).
        hash_algorithm: ``"sha1"`` or ``"sha256"``. Defaults to ``"sha256"``
            for XAdES; ``XMLDSigSigner`` passes the algorithm derived from
            its configured ``SignatureMethod``.
    """
    try:
        from cryptography.hazmat.primitives import hashes  # noqa: PLC0415
        from cryptography.hazmat.primitives.asymmetric import padding  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "cryptography>=42.0.0 is required for XML signing. "
            "Install: pip install 'mcp-einvoicing-core[xml-sign]'"
        ) from exc
    hash_obj = {"sha1": hashes.SHA1(), "sha256": hashes.SHA256()}[hash_algorithm]
    return private_key.sign(data, padding.PKCS1v15(), hash_obj)  # type: ignore[union-attr]


class XAdESEPESSigner(BaseDocumentSigner):
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

    def __init__(
        self,
        config: XAdESSignerConfig,
        *,
        _preloaded_cert_info: Optional[_CertInfo] = None,
    ) -> None:
        self._config = config
        # _preloaded_cert_info is used by the signer microservice which loads the
        # PKCS#12 once at process startup and passes the parsed material directly,
        # avoiding a second disk read and keeping the cert path out of tool handlers.
        self._cert_info: Optional[_CertInfo] = _preloaded_cert_info

    def load_credentials(self) -> None:
        """Load the PKCS#12 certificate and private key into memory."""
        self._cert_info = _load_pkcs12(
            self._config.cert_path, self._config.cert_password
        )

    def _get_cert_info(self) -> _CertInfo:
        if self._cert_info is None:
            self.load_credentials()
        return self._cert_info  # type: ignore[return-value]

    def verify(self, signed_document: bytes) -> bool:
        """XAdES signature verification is not yet implemented.

        Use an external XAdES verifier (e.g. DSS, VerifyCades) to validate
        signatures produced by this signer.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "XAdES signature verification is not yet implemented in XAdESEPESSigner. "
            "Use an external XAdES verifier (ETSI DSS, VerifyCades, or xmlsec) to "
            "validate signatures produced by this signer."
        )

    def cleanup(self) -> None:
        """Drop references to the private key and certificate material.

        Call from a ``try/finally`` block after each signing session to reduce
        the window during which key material is reachable in process memory.
        Python cannot truly zero ``bytes`` objects, but dropping the reference
        allows the GC to reclaim the memory sooner and prevents accidental
        re-use of the key after the session ends.

        After ``cleanup()``, the next ``sign()`` call will reload credentials
        from disk via ``load_credentials()``.
        """
        self._cert_info = None

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
        root = safe_fromstring(xml_bytes)
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


# ---------------------------------------------------------------------------
# Plain enveloped XML-DSig (no XAdES) — BR NF-e/NFC-e and friends
# ---------------------------------------------------------------------------


@dataclass
class XMLDSigSignerConfig:
    """Configuration for plain enveloped XML-DSig signing.

    Unlike :class:`XAdESSignerConfig`, this produces a bare ``ds:Signature``
    with a single ``ds:Reference`` to a specific element by ``Id`` — no
    ``xades:QualifyingProperties``. This matches the NF-e/NFC-e signature
    shape (MOC 7.0): ``ds:Signature`` is a sibling of ``infNFe`` and the
    ``ds:Reference`` ``URI`` points at ``infNFe``'s ``Id`` attribute
    (``#NFe<chave_acesso>``).

    Attributes:
        cert_path: Path to the PKCS#12 (.p12 / .pfx) certificate file.
        cert_password: Passphrase for the PKCS#12 file, or ``None`` if
            unprotected.
        signature_algorithm: ``ds:SignatureMethod`` algorithm URI. Defaults
            to RSA-SHA1, confirmed against MOC 7.0 Table 4-2 for NF-e/NFC-e.
            XAdES-based formats hardcode SHA-256; pass the SHA-256 URI here
            if reusing this signer for a format that requires it.
        digest_algorithm: ``ds:DigestMethod`` algorithm URI used for the
            ``ds:Reference`` digest. Defaults to SHA-1, matching
            ``signature_algorithm``.
        signed_element_local_name: Local name (any namespace) of the element
            that carries the ``Id`` attribute referenced by the
            ``ds:Reference``. Defaults to ``"infNFe"`` for NF-e/NFC-e; CT-e
            and NFS-e reuse with their own element name.
        id_attribute: Name of the attribute on *signed_element_local_name*
            holding the value referenced as ``URI="#<value>"``. Defaults to
            ``"Id"``.
    """

    cert_path: str
    cert_password: Optional[str] = None
    signature_algorithm: str = _RSA_SHA1_SIGN_ALG
    digest_algorithm: str = _SHA1_DIGEST_ALG
    signed_element_local_name: str = "infNFe"
    id_attribute: str = "Id"


def _build_xmldsig_signed_info(
    reference_uri: str,
    digest_value: str,
    signature_algorithm: str,
    digest_algorithm: str,
) -> etree._Element:
    """Build a ``ds:SignedInfo`` with a single enveloped-signature Reference.

    The ``ds:Reference/ds:Transforms`` element carries two ``ds:Transform``
    entries — enveloped-signature followed by C14N — per MOC 7.0 (NF-e/NFC-e
    signature figure, ``[Verified locally]``) and the bundled NF-e
    ``xmldsig-core-schema_v1.01.xsd``, whose ``TransformsType`` requires
    exactly two ``Transform`` elements.
    """
    nsmap = {_DS_PREFIX: _DS}
    si = etree.Element(_qn(_DS, "SignedInfo"), nsmap=nsmap)

    cm = etree.SubElement(si, _qn(_DS, "CanonicalizationMethod"))
    cm.set("Algorithm", _C14N_ALG)

    sm = etree.SubElement(si, _qn(_DS, "SignatureMethod"))
    sm.set("Algorithm", signature_algorithm)

    ref = etree.SubElement(si, _qn(_DS, "Reference"))
    ref.set("URI", reference_uri)
    transforms = etree.SubElement(ref, _qn(_DS, "Transforms"))
    t1 = etree.SubElement(transforms, _qn(_DS, "Transform"))
    t1.set("Algorithm", _ENVELOPED_TRANSFORM)
    t2 = etree.SubElement(transforms, _qn(_DS, "Transform"))
    t2.set("Algorithm", _C14N_ALG)
    dm = etree.SubElement(ref, _qn(_DS, "DigestMethod"))
    dm.set("Algorithm", digest_algorithm)
    etree.SubElement(ref, _qn(_DS, "DigestValue")).text = digest_value

    return si


class XMLDSigSigner(BaseDocumentSigner):
    """Apply a plain enveloped XML-DSig signature (no XAdES) to an XML document.

    The signer locates the element identified by
    ``config.signed_element_local_name`` (default ``infNFe``), reads its
    ``Id`` attribute, and builds a ``ds:Signature`` whose single
    ``ds:Reference`` points at that element via ``URI="#<id>"`` with the
    enveloped-signature transform. The ``ds:Signature`` element is appended
    as the last child of the document root (sibling of ``infNFe`` inside
    ``NFe``), matching the placement confirmed against MOC 7.0.

    Example::

        config = XMLDSigSignerConfig(
            cert_path="/path/to/cert.p12",
            cert_password="secret",
        )
        signer = XMLDSigSigner(config)
        signed_xml = signer.sign(unsigned_nfe_xml_bytes)
    """

    def __init__(
        self,
        config: XMLDSigSignerConfig,
        *,
        _preloaded_cert_info: Optional[_CertInfo] = None,
    ) -> None:
        self._config = config
        self._cert_info: Optional[_CertInfo] = _preloaded_cert_info

    def load_credentials(self) -> None:
        """Load the PKCS#12 certificate and private key into memory."""
        self._cert_info = _load_pkcs12(
            self._config.cert_path, self._config.cert_password
        )

    def _get_cert_info(self) -> _CertInfo:
        if self._cert_info is None:
            self.load_credentials()
        return self._cert_info  # type: ignore[return-value]

    def verify(self, signed_document: bytes) -> bool:
        """XML-DSig signature verification is not yet implemented.

        Use an external XML-DSig verifier (e.g. xmlsec, the SEFAZ
        validation webservice) to validate signatures produced by this
        signer.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "XML-DSig signature verification is not yet implemented in "
            "XMLDSigSigner. Use an external verifier (xmlsec, or the SEFAZ "
            "validation webservice) to validate signatures produced by this "
            "signer."
        )

    def cleanup(self) -> None:
        """Drop references to the private key and certificate material.

        See :meth:`XAdESEPESSigner.cleanup` for the rationale. After
        ``cleanup()``, the next ``sign()`` call reloads credentials from
        disk via ``load_credentials()``.
        """
        self._cert_info = None

    def sign(self, xml_bytes: bytes) -> bytes:
        """Return *xml_bytes* with an embedded enveloped XML-DSig signature.

        Args:
            xml_bytes: Well-formed XML document containing an element named
                ``config.signed_element_local_name`` with an
                ``config.id_attribute`` attribute (e.g. ``<infNFe Id="NFe...">``).

        Returns:
            UTF-8 XML document with ``ds:Signature`` appended as the last
            child of the document root.

        Raises:
            ImportError: If ``cryptography`` is not installed.
            ValueError: If the PKCS#12 file contains no certificate or key,
                or if the signed element / Id attribute is missing.
        """
        cert_info = self._get_cert_info()

        root = safe_fromstring(xml_bytes)

        target = root.find(f".//{{*}}{self._config.signed_element_local_name}")
        if target is None:
            raise ValueError(
                f"No <{self._config.signed_element_local_name}> element found "
                f"in document"
            )
        element_id = target.get(self._config.id_attribute)
        if not element_id:
            raise ValueError(
                f"<{self._config.signed_element_local_name}> has no "
                f"'{self._config.id_attribute}' attribute to reference"
            )
        reference_uri = f"#{element_id}"

        # Digest of the referenced element's C14N (enveloped-signature
        # transform is a no-op here: no ds:Signature exists yet inside it)
        element_digest = _digest_b64(_c14n(target), self._config.digest_algorithm)

        si_elem = _build_xmldsig_signed_info(
            reference_uri,
            element_digest,
            self._config.signature_algorithm,
            self._config.digest_algorithm,
        )
        si_c14n = _c14n(si_elem)
        hash_name = _SIGN_ALG_HASH_NAMES.get(self._config.signature_algorithm, "sha256")
        sig_value_bytes = _sign_bytes(cert_info.private_key, si_c14n, hash_name)
        sig_value_b64 = base64.b64encode(sig_value_bytes).decode()

        nsmap = {_DS_PREFIX: _DS}
        sig_elem = etree.Element(_qn(_DS, "Signature"), nsmap=nsmap)
        sig_elem.append(si_elem)

        sv = etree.SubElement(sig_elem, _qn(_DS, "SignatureValue"))
        sv.text = sig_value_b64

        sig_elem.append(_build_key_info(cert_info))

        # Last child of the document root (sibling of infNFe inside NFe)
        root.append(sig_elem)

        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
