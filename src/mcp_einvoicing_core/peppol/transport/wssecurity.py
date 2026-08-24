"""WS-Security X.509 message-level signing for outbound Peppol AS4 messages.

Implements the signing side of the Peppol AS4 Profile v2.0.3 (vendored:
``specs/peppol/Peppol-AS4-Profile-2.0.3.pdf``) section 4.7 "Use of Peppol
PKI": a ``wsse:BinarySecurityToken`` (ValueType ``...#X509v3``, confirmed
2.0.3 section 4.7) carrying the sending Access Point's certificate, and a
``ds:Signature`` over the SOAP Body, the ``eb:Messaging`` header, and each
MIME attachment payload.

The Peppol AS4 Profile itself defers the exact WS-Security wire format
(canonicalization algorithm, Reference/Transform shapes) to
[CEFeDeliveryAS4] v1.14 section 3.2.6 and, transitively, OASIS WS-Security
SOAP Message Security 1.1 / X.509 Token Profile 1.1 — neither of which is
vendored locally (see ``specs/peppol/README.md``). This module implements
those two OASIS standards directly (they are stable, general-purpose XML
security mechanisms, not Peppol-specific or regulatory content):

- Canonicalization: Exclusive XML Canonicalization (``xml-exc-c14n#``), the
  standard choice for WS-Security signatures over SOAP documents — required
  because SOAP header siblings rely on namespace declarations inherited from
  ancestor elements, which plain (non-exclusive) C14N does not canonicalize
  consistently in isolation from the whole document.
  [NEED: verify against CEF eDelivery AS4 v1.14 section 3.2.6 once that
  document is available locally.]
- Attachment references: the SOAP Message Security 1.1 SwA Profile
  ``Attachment-Content-Signature-Transform``, digesting the raw (pre-MIME-
  encoding) attachment bytes. This is the standard OASIS mechanism for
  signing MIME attachments in a WS-Security-protected SOAP message and is
  how every mainstream AS4/ebMS3 implementation (Domibus, phase4, ...)
  signs the compressed invoice payload attachment.
- KeyInfo: a ``wsse:SecurityTokenReference`` pointing at the
  ``BinarySecurityToken`` by ``wsu:Id`` (Direct Reference), the standard
  WS-Security X.509 Token Profile pattern — rather than re-embedding the raw
  certificate a second time via ``ds:X509Data``.

Message-level encryption (``PMode[].Security.X509.Encryption.Certificate``
in AS4 Profile table 5) is out of scope for this module — signing only.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_der_x509_certificate
from lxml import etree

from mcp_einvoicing_core.digital_signature import _qn, _sign_bytes

_WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
_WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
_DS_NS = "http://www.w3.org/2000/09/xmldsig#"
_SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
_EBMS_NS = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/"

_WSSE_PREFIX = "wsse"
_WSU_PREFIX = "wsu"
_DS_PREFIX = "ds"

_BST_VALUE_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
)
_BST_ENCODING_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0"
    "#Base64Binary"
)
_EXC_C14N_ALG = "http://www.w3.org/2001/10/xml-exc-c14n#"
_RSA_SHA256_ALG = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
_SHA256_DIGEST_ALG = "http://www.w3.org/2001/04/xmlenc#sha256"
_ATTACHMENT_TRANSFORM = (
    "http://docs.oasis-open.org/wss/oasis-wss-SwAProfile-1.1"
    "#Attachment-Content-Signature-Transform"
)


@dataclass
class SignedAttachment:
    """A MIME attachment to be covered by the WS-Security signature.

    Attributes:
        content_id: The MIME ``Content-Id`` value, without the ``cid:``
            prefix or angle brackets (e.g. ``"invoice@peppol.eu"``).
        content: The raw attachment bytes as transmitted (post-compression,
            pre-MIME-transfer-encoding — this implementation always uses
            ``Content-Transfer-Encoding: binary``, so these are the exact
            bytes the digest must cover).
    """

    content_id: str
    content: bytes


def _exc_c14n(element: etree._Element) -> bytes:
    """Return the Exclusive XML Canonicalization (no comments) of *element*."""
    return etree.tostring(element, method="c14n", exclusive=True, with_comments=False)


def _sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def _find_first(root: etree._Element, ns: str, local: str) -> etree._Element | None:
    return root.find(f".//{{{ns}}}{local}")


def sign_as4_message(
    soap_bytes: bytes,
    attachments: list[SignedAttachment],
    cert_der: bytes,
    private_key: object,
) -> bytes:
    """Return *soap_bytes* with a ``wsse:Security`` header inserted, signing
    the SOAP Body, the ``eb:Messaging`` header, and each attachment in
    *attachments*.

    Args:
        soap_bytes: The unsigned ebMS3/AS4 SOAP envelope, as produced by
            ``AS4MessageEnvelope.build()``.
        attachments: MIME attachments to cover with the signature (normally
            the single compressed invoice payload).
        cert_der: DER-encoded X.509 certificate of the signing Access Point.
        private_key: An RSA private key object from ``cryptography``,
            matching *cert_der*.

    Returns:
        UTF-8 XML bytes of the SOAP envelope with ``wsse:Security`` inserted
        as the last child of ``S12:Header``.
    """
    root = etree.fromstring(soap_bytes)

    header = _find_first(root, _SOAP_NS, "Header")
    if header is None:
        raise ValueError("SOAP envelope has no S12:Header to insert wsse:Security into.")
    body = _find_first(root, _SOAP_NS, "Body")
    if body is None:
        raise ValueError("SOAP envelope has no S12:Body element.")
    messaging = _find_first(root, _EBMS_NS, "Messaging")
    if messaging is None:
        raise ValueError("SOAP envelope has no eb:Messaging header to sign.")

    sig_uuid = uuid.uuid4().hex[:16]
    body_id = f"Body-{sig_uuid}"
    messaging_id = f"Messaging-{sig_uuid}"
    bst_id = f"X509-{sig_uuid}"

    body.set(_qn(_WSU_NS, "Id"), body_id)
    messaging.set(_qn(_WSU_NS, "Id"), messaging_id)

    references: list[tuple[str, str, str | None]] = []
    # (uri, digest_b64, transform_algorithm) — transform_algorithm None means exc-c14n
    references.append((f"#{body_id}", _sha256_b64(_exc_c14n(body)), None))
    references.append((f"#{messaging_id}", _sha256_b64(_exc_c14n(messaging)), None))
    for attachment in attachments:
        digest = _sha256_b64(attachment.content)
        references.append((f"cid:{attachment.content_id}", digest, _ATTACHMENT_TRANSFORM))

    signed_info = _build_signed_info(references)
    signed_info_c14n = _exc_c14n(signed_info)
    signature_value = base64.b64encode(
        _sign_bytes(private_key, signed_info_c14n, "sha256")
    ).decode()

    nsmap = {_WSSE_PREFIX: _WSSE_NS, _WSU_PREFIX: _WSU_NS, _DS_PREFIX: _DS_NS}
    security = etree.Element(_qn(_WSSE_NS, "Security"), nsmap=nsmap)
    security.set(_qn(_SOAP_NS, "mustUnderstand"), "true")

    bst = etree.SubElement(security, _qn(_WSSE_NS, "BinarySecurityToken"))
    bst.set("EncodingType", _BST_ENCODING_TYPE)
    bst.set("ValueType", _BST_VALUE_TYPE)
    bst.set(_qn(_WSU_NS, "Id"), bst_id)
    bst.text = base64.b64encode(cert_der).decode()

    signature = etree.SubElement(security, _qn(_DS_NS, "Signature"))
    signature.append(signed_info)
    sv = etree.SubElement(signature, _qn(_DS_NS, "SignatureValue"))
    sv.text = signature_value
    signature.append(_build_key_info(bst_id))

    header.append(security)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def _build_signed_info(references: list[tuple[str, str, str | None]]) -> etree._Element:
    si = etree.Element(_qn(_DS_NS, "SignedInfo"), nsmap={_DS_PREFIX: _DS_NS})

    cm = etree.SubElement(si, _qn(_DS_NS, "CanonicalizationMethod"))
    cm.set("Algorithm", _EXC_C14N_ALG)

    sm = etree.SubElement(si, _qn(_DS_NS, "SignatureMethod"))
    sm.set("Algorithm", _RSA_SHA256_ALG)

    for uri, digest_b64, transform_alg in references:
        ref = etree.SubElement(si, _qn(_DS_NS, "Reference"))
        ref.set("URI", uri)
        transforms = etree.SubElement(ref, _qn(_DS_NS, "Transforms"))
        t = etree.SubElement(transforms, _qn(_DS_NS, "Transform"))
        t.set("Algorithm", transform_alg or _EXC_C14N_ALG)
        dm = etree.SubElement(ref, _qn(_DS_NS, "DigestMethod"))
        dm.set("Algorithm", _SHA256_DIGEST_ALG)
        etree.SubElement(ref, _qn(_DS_NS, "DigestValue")).text = digest_b64

    return si


@dataclass
class AS4SignatureVerificationResult:
    """Result of `verify_as4_signature`."""

    signature_valid: bool
    certificate_der: bytes | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def error(self) -> str | None:
        return "; ".join(self.errors) if self.errors else None


def verify_as4_signature(
    soap_bytes: bytes, attachments: list[SignedAttachment]
) -> AS4SignatureVerificationResult:
    """Verify a ``wsse:Security`` header produced by `sign_as4_message`.

    Recomputes every Reference digest (Body/Messaging by ``wsu:Id``,
    attachments by ``cid:``) and verifies the ``ds:SignatureValue`` against
    the certificate embedded in the ``BinarySecurityToken``. Does **not**
    chain-validate the certificate — pair with
    ``mcp_einvoicing_core.peppol.trust.validate_certificate_chain`` for that.

    Args:
        soap_bytes: The received SOAP envelope (with ``wsse:Security`` header).
        attachments: The MIME attachments received alongside the envelope,
            keyed by their ``Content-Id`` (without ``cid:`` prefix or angle
            brackets) — see `SignedAttachment`.
    """
    root = etree.fromstring(soap_bytes)

    security = root.find(f".//{{{_WSSE_NS}}}Security")
    if security is None:
        return AS4SignatureVerificationResult(False, errors=["No wsse:Security header found."])

    bst = security.find(_qn(_WSSE_NS, "BinarySecurityToken"))
    if bst is None or not (bst.text or "").strip():
        return AS4SignatureVerificationResult(
            False, errors=["No BinarySecurityToken found in wsse:Security."]
        )
    try:
        cert_der = base64.b64decode(bst.text.strip())
        cert = load_der_x509_certificate(cert_der)
    except Exception as exc:  # noqa: BLE001 - malformed BST content
        return AS4SignatureVerificationResult(False, errors=[f"Invalid BinarySecurityToken: {exc}"])

    signature = security.find(_qn(_DS_NS, "Signature"))
    if signature is None:
        return AS4SignatureVerificationResult(
            False, certificate_der=cert_der, errors=["No ds:Signature found in wsse:Security."]
        )
    signed_info = signature.find(_qn(_DS_NS, "SignedInfo"))
    signature_value_el = signature.find(_qn(_DS_NS, "SignatureValue"))
    if signed_info is None or signature_value_el is None:
        return AS4SignatureVerificationResult(
            False, certificate_der=cert_der, errors=["ds:Signature missing SignedInfo/SignatureValue."]
        )

    attachments_by_cid = {a.content_id: a.content for a in attachments}
    errors: list[str] = []

    for ref in signed_info.findall(_qn(_DS_NS, "Reference")):
        uri = ref.get("URI", "")
        digest_value_el = ref.find(_qn(_DS_NS, "DigestValue"))
        expected_digest = (digest_value_el.text or "").strip() if digest_value_el is not None else ""

        if uri.startswith("cid:"):
            content_id = uri[len("cid:") :]
            content = attachments_by_cid.get(content_id)
            if content is None:
                errors.append(f"Reference {uri!r}: attachment not supplied for verification.")
                continue
            actual_digest = _sha256_b64(content)
        elif uri.startswith("#"):
            target_id = uri[1:]
            matches = root.xpath(
                "//*[@wsu:Id=$tid]", namespaces={"wsu": _WSU_NS}, tid=target_id
            )
            if not matches:
                errors.append(f"Reference {uri!r}: no element with matching wsu:Id found.")
                continue
            actual_digest = _sha256_b64(_exc_c14n(matches[0]))
        else:
            errors.append(f"Reference {uri!r}: unsupported URI scheme.")
            continue

        if actual_digest != expected_digest:
            errors.append(f"Reference {uri!r}: digest mismatch.")

    if errors:
        return AS4SignatureVerificationResult(False, certificate_der=cert_der, errors=errors)

    signed_info_c14n = _exc_c14n(signed_info)
    try:
        signature_bytes = base64.b64decode((signature_value_el.text or "").strip())
        cert.public_key().verify(  # type: ignore[union-attr]
            signature_bytes, signed_info_c14n, padding.PKCS1v15(), hashes.SHA256()
        )
    except InvalidSignature:
        return AS4SignatureVerificationResult(
            False, certificate_der=cert_der, errors=["SignatureValue does not verify."]
        )
    except Exception as exc:  # noqa: BLE001 - malformed signature value / unsupported key type
        return AS4SignatureVerificationResult(
            False, certificate_der=cert_der, errors=[f"Signature verification error: {exc}"]
        )

    return AS4SignatureVerificationResult(True, certificate_der=cert_der)


def _build_key_info(bst_id: str) -> etree._Element:
    """Build a ``ds:KeyInfo`` referencing the ``BinarySecurityToken`` by Id
    (WS-Security X.509 Token Profile "Direct Reference")."""
    ki = etree.Element(
        _qn(_DS_NS, "KeyInfo"), nsmap={_DS_PREFIX: _DS_NS, _WSSE_PREFIX: _WSSE_NS}
    )
    str_el = etree.SubElement(ki, _qn(_WSSE_NS, "SecurityTokenReference"))
    ref = etree.SubElement(str_el, _qn(_WSSE_NS, "Reference"))
    ref.set("URI", f"#{bst_id}")
    ref.set("ValueType", _BST_VALUE_TYPE)
    return ki
