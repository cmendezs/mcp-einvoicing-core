"""Peppol PKI trust-store validation (CORE-PEPPOL-TRUST-1).

Certificate chain validation, revocation checking, and SMP signed-metadata
verification for the OpenPeppol application-level PKI — the certificates
used to sign AS4 messages and (optionally) SMP service metadata, distinct
from the TLS certificates covered by the vendored "Peppol Policy for
Transport Security" v1.1.0 (``specs/peppol/PEPPOL-EDN-Policy-for-Transport-Security-1.1.0-2020-04-20.pdf``,
CC BY-NC-ND). That policy document only covers TLS (public-CA-issued,
non-self-signed, SSL Labs grade A) — it does not publish the OpenPeppol PKI
root/intermediate certificates themselves, which OpenPeppol distributes
separately per environment (Test/Production).

**Guarded until trust anchors are supplied.** This module's chain and
revocation checks require the deployer to supply the OpenPeppol PKI root
and intermediate CA certificates locally (they are not bundled — this
package ships no OpenPeppol PKI material). Point
``EINVOICING_PEPPOL_PKI_DIR`` at a directory containing ``test/`` and
``prod/`` subdirectories of PEM-encoded root/intermediate certificates.
Until that is configured, every function in this module reports
``trust_anchors_configured: False`` / status ``"trust-anchors-not-configured"``
rather than failing closed or silently passing.

Consumed by:
  - The AS4 inbound receiver (``peppol.transport.inbound``), to validate the
    sender Access Point's signing certificate.
  - AS4 outbound transmission, to validate the receiver Access Point's
    certificate fetched from SMP (not yet wired — see roadmap).
  - ``PeppolSMPClient`` via the opt-in ``verify_smp_signatures`` constructor
    flag (default off, non-breaking), to verify a ``SignedServiceMetadata``
    response's enveloped ``ds:Signature`` before trusting the AS4 endpoint
    it advertises.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import ocsp
from cryptography.x509.verification import ExtensionPolicy, PolicyBuilder, Store, VerificationError
from lxml import etree

from mcp_einvoicing_core.peppol import PeppolEnvironment
from mcp_einvoicing_core.xml_utils import safe_fromstring

logger = logging.getLogger(__name__)

_ENV_VAR = "EINVOICING_PEPPOL_PKI_DIR"

_DS_NS = "http://www.w3.org/2000/09/xmldsig#"
_ENVELOPED_TRANSFORM = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
_C14N_ALG = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
_EXC_C14N_ALG = "http://www.w3.org/2001/10/xml-exc-c14n#"

_DIGEST_HASH_NAMES = {
    "http://www.w3.org/2000/09/xmldsig#sha1": hashes.SHA1,
    "http://www.w3.org/2001/04/xmlenc#sha256": hashes.SHA256,
    "http://www.w3.org/2001/04/xmldsig-more#sha384": hashes.SHA384,
    "http://www.w3.org/2001/04/xmlenc#sha512": hashes.SHA512,
}
_SIGNATURE_HASH_NAMES = {
    "http://www.w3.org/2000/09/xmldsig#rsa-sha1": hashes.SHA1,
    "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256": hashes.SHA256,
    "http://www.w3.org/2001/04/xmldsig-more#rsa-sha384": hashes.SHA384,
    "http://www.w3.org/2001/04/xmldsig-more#rsa-sha512": hashes.SHA512,
}


class PeppolPKINotConfiguredError(Exception):
    """EINVOICING_PEPPOL_PKI_DIR is unset, not a directory, or has no
    root/intermediate certificates under the requested environment subdir."""


class PeppolTrustStore:
    """Loads OpenPeppol PKI root/intermediate CA certificates from
    ``EINVOICING_PEPPOL_PKI_DIR/{test,prod}/``.

    Accepts PEM files with extension ``.pem``, ``.crt``, or ``.cer``, each
    containing one or more concatenated PEM certificates.
    """

    def __init__(self, environment: PeppolEnvironment) -> None:
        self._environment = environment

    def _subdir_name(self) -> str:
        return "test" if self._environment == PeppolEnvironment.TEST else "prod"

    def certs_dir(self) -> Path:
        raw = os.environ.get(_ENV_VAR, "").strip()
        if not raw:
            raise PeppolPKINotConfiguredError(
                f"{_ENV_VAR} is not set. Peppol PKI trust validation requires a "
                "local copy of the OpenPeppol root/intermediate CA certificates "
                "(Test and Production environments), not bundled with this "
                f"package. Set {_ENV_VAR} to a directory containing 'test/' and "
                "'prod/' subdirectories of PEM-encoded certificates."
            )
        directory = Path(raw) / self._subdir_name()
        if not directory.is_dir():
            raise PeppolPKINotConfiguredError(
                f"{directory} is not a directory. Expected "
                f"{_ENV_VAR}/{self._subdir_name()}/ to contain PEM-encoded "
                "OpenPeppol root/intermediate CA certificates."
            )
        return directory

    def load_root_certs(self) -> list[x509.Certificate]:
        """Load and parse every PEM certificate under the environment subdir.

        Raises:
            PeppolPKINotConfiguredError: If unconfigured, or the directory
                contains no readable certificates.
        """
        directory = self.certs_dir()
        certs: list[x509.Certificate] = []
        for path in sorted(directory.glob("*")):
            if path.suffix.lower() not in (".pem", ".crt", ".cer"):
                continue
            try:
                certs.extend(_load_pem_certs(path.read_bytes()))
            except ValueError as exc:
                logger.warning("Could not parse certificate file %s: %s", path, exc)
        if not certs:
            raise PeppolPKINotConfiguredError(
                f"No readable .pem/.crt/.cer certificates found under {directory}."
            )
        return certs


def _load_pem_certs(pem_bytes: bytes) -> list[x509.Certificate]:
    """Parse one or more concatenated PEM certificates from a single file."""
    certs: list[x509.Certificate] = []
    marker = b"-----BEGIN CERTIFICATE-----"
    for chunk in pem_bytes.split(marker)[1:]:
        pem = marker + chunk.split(b"-----END CERTIFICATE-----")[0] + b"-----END CERTIFICATE-----\n"
        certs.append(x509.load_pem_x509_certificate(pem))
    if not certs:
        raise ValueError("No PEM certificate blocks found.")
    return certs


def _load_cert(cert_bytes: bytes) -> x509.Certificate:
    if b"-----BEGIN CERTIFICATE-----" in cert_bytes:
        return x509.load_pem_x509_certificate(cert_bytes)
    return x509.load_der_x509_certificate(cert_bytes)


def validate_certificate_chain(
    leaf_cert: bytes,
    environment: PeppolEnvironment,
    *,
    intermediates: list[bytes] | None = None,
    validation_time: datetime | None = None,
) -> dict[str, Any]:
    """Validate *leaf_cert* chains to a configured OpenPeppol PKI root.

    Args:
        leaf_cert: PEM or DER encoded certificate to validate.
        environment: Which OpenPeppol PKI environment (Test/Production) to
            validate against.
        intermediates: Optional PEM/DER intermediate certificates to include
            in the candidate chain.
        validation_time: Point in time to validate against (defaults to now).

    Returns:
        A dict with ``trust_anchors_configured`` (bool), ``valid`` (bool),
        ``status`` (one of "trust-anchors-not-configured", "valid",
        "invalid"), and ``error`` (str | None).
    """
    try:
        store = PeppolTrustStore(environment)
        roots = store.load_root_certs()
    except PeppolPKINotConfiguredError as exc:
        return {
            "trust_anchors_configured": False,
            "valid": False,
            "status": "trust-anchors-not-configured",
            "error": str(exc),
        }

    leaf = _load_cert(leaf_cert)
    intermediate_certs = [_load_cert(c) for c in (intermediates or [])]

    builder = PolicyBuilder().store(Store(roots))
    builder = builder.time(validation_time or datetime.now(UTC))
    # Peppol AS4/SMP application-level certificates are not TLS certificates
    # and are not required to carry a subjectAltName — the webpki-derived
    # default end-entity policy does require one, so it is relaxed to
    # ExtensionPolicy.permit_all() here. The CA policy keeps webpki defaults
    # (BasicConstraints/KeyUsage enforcement on issuers).
    builder = builder.extension_policies(
        ca_policy=ExtensionPolicy.webpki_defaults_ca(),
        ee_policy=ExtensionPolicy.permit_all(),
    )
    verifier = builder.build_client_verifier()

    try:
        verified = verifier.verify(leaf, intermediate_certs)
    except VerificationError as exc:
        return {
            "trust_anchors_configured": True,
            "valid": False,
            "status": "invalid",
            "error": str(exc),
        }

    return {
        "trust_anchors_configured": True,
        "valid": True,
        "status": "valid",
        "chain_length": len(verified.chain),
        "error": None,
    }


@dataclass
class RevocationCheckResult:
    """Result of `check_revocation`."""

    checked: bool
    revoked: bool | None
    method: str | None
    error: str | None = None


async def check_revocation(
    cert_bytes: bytes,
    issuer_cert_bytes: bytes,
    *,
    http_timeout: float = 10.0,
) -> RevocationCheckResult:
    """Check whether *cert_bytes* is revoked, via OCSP (falling back to CRL).

    Honors the certificate's Authority Information Access (OCSP responder
    URI) and CRL Distribution Points extensions. Returns
    ``checked=False`` if the certificate carries neither extension (nothing
    to query).

    Args:
        cert_bytes: PEM or DER encoded certificate to check.
        issuer_cert_bytes: PEM or DER encoded issuing CA certificate
            (required to build the OCSP request).
        http_timeout: HTTP timeout in seconds for OCSP/CRL fetches.
    """
    cert = _load_cert(cert_bytes)
    issuer = _load_cert(issuer_cert_bytes)

    ocsp_url = _find_ocsp_url(cert)
    if ocsp_url:
        result = await _check_ocsp(cert, issuer, ocsp_url, http_timeout)
        if result is not None:
            return result

    crl_url = _find_crl_url(cert)
    if crl_url:
        return await _check_crl(cert, crl_url, http_timeout)

    return RevocationCheckResult(
        checked=False,
        revoked=None,
        method=None,
        error="Certificate carries neither an OCSP responder URI nor a CRL "
        "distribution point; nothing to query.",
    )


def _find_ocsp_url(cert: x509.Certificate) -> str | None:
    try:
        aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
    except x509.ExtensionNotFound:
        return None
    for desc in aia:
        if desc.access_method == x509.AuthorityInformationAccessOID.OCSP:
            return desc.access_location.value
    return None


def _find_crl_url(cert: x509.Certificate) -> str | None:
    try:
        cdp = cert.extensions.get_extension_for_class(x509.CRLDistributionPoints).value
    except x509.ExtensionNotFound:
        return None
    for point in cdp:
        if point.full_name:
            for name in point.full_name:
                if isinstance(name, x509.UniformResourceIdentifier):
                    return name.value
    return None


async def _check_ocsp(
    cert: x509.Certificate, issuer: x509.Certificate, ocsp_url: str, http_timeout: float
) -> RevocationCheckResult | None:
    """Return a result, or None if the OCSP request itself could not be
    completed (caller should fall back to CRL)."""
    try:
        request = ocsp.OCSPRequestBuilder().add_certificate(cert, issuer, hashes.SHA1()).build()
        request_der = request.public_bytes(serialization.Encoding.DER)
    except Exception as exc:  # noqa: BLE001 - malformed cert data, fall back to CRL
        logger.warning("Could not build OCSP request: %s", exc)
        return None

    try:
        async with httpx.AsyncClient(timeout=http_timeout, trust_env=False) as client:
            response = await client.post(
                ocsp_url,
                content=request_der,
                headers={"Content-Type": "application/ocsp-request"},
            )
        if not response.is_success:
            logger.warning("OCSP responder %s returned HTTP %d", ocsp_url, response.status_code)
            return None
        ocsp_response = ocsp.load_der_ocsp_response(response.content)
    except Exception as exc:  # noqa: BLE001 - network/parse failure, fall back to CRL
        logger.warning("OCSP request to %s failed: %s", ocsp_url, exc)
        return None

    if ocsp_response.response_status != ocsp.OCSPResponseStatus.SUCCESSFUL:
        return None

    revoked = ocsp_response.certificate_status == ocsp.OCSPCertStatus.REVOKED
    return RevocationCheckResult(checked=True, revoked=revoked, method="ocsp")


async def _check_crl(
    cert: x509.Certificate, crl_url: str, http_timeout: float
) -> RevocationCheckResult:
    try:
        async with httpx.AsyncClient(timeout=http_timeout, trust_env=False) as client:
            response = await client.get(crl_url)
        if not response.is_success:
            return RevocationCheckResult(
                checked=False,
                revoked=None,
                method="crl",
                error=f"CRL fetch from {crl_url} returned HTTP {response.status_code}.",
            )
        content = response.content
        crl = (
            x509.load_pem_x509_crl(content)
            if b"-----BEGIN X509 CRL-----" in content
            else x509.load_der_x509_crl(content)
        )
    except Exception as exc:  # noqa: BLE001 - network/parse failure
        return RevocationCheckResult(
            checked=False, revoked=None, method="crl", error=f"CRL check failed: {exc}"
        )

    revoked = crl.get_revoked_certificate_by_serial_number(cert.serial_number) is not None
    return RevocationCheckResult(checked=True, revoked=revoked, method="crl")


# ---------------------------------------------------------------------------
# Enveloped XML-DSig verification (SMP SignedServiceMetadata)
# ---------------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _c14n_for_algorithm(element: etree._Element, algorithm: str) -> bytes:
    if algorithm == _EXC_C14N_ALG:
        return etree.tostring(element, method="c14n", exclusive=True, with_comments=False)
    return etree.tostring(element, method="c14n", exclusive=False, with_comments=False)


def verify_smp_signature(
    signed_xml: bytes,
    *,
    environment: PeppolEnvironment | None = None,
) -> dict[str, Any]:
    """Verify the enveloped ``ds:Signature`` on a busdox ``SignedServiceMetadata``
    document (or any other single-``ds:Signature`` enveloped-XML-DSig document).

    SMP does not verify SMP response signatures today
    (``PeppolSMPClient._parse_service_metadata`` only reads the embedded
    ``<Certificate>`` element) — this function is the standalone building
    block for the opt-in ``verify_smp_signatures`` hook on `PeppolSMPClient`.

    Args:
        signed_xml: The full signed document bytes.
        environment: If supplied, also chain-validate the signer certificate
            against the OpenPeppol PKI for this environment (guarded — see
            `validate_certificate_chain`). If None, only the cryptographic
            signature is checked, not the certificate's trust chain.

    Returns:
        A dict with ``signature_valid`` (bool), ``error`` (str | None), and,
        when *environment* is supplied, ``chain`` (the `validate_certificate_chain`
        result dict).
    """
    try:
        root = safe_fromstring(signed_xml)
    except etree.XMLSyntaxError as exc:
        return {"signature_valid": False, "error": f"XML parse error: {exc}"}

    signature_el = None
    for el in root.iter():
        if _local(el.tag) == "Signature" and el.tag.startswith(f"{{{_DS_NS}}}"):
            signature_el = el
            break
    if signature_el is None:
        return {"signature_valid": False, "error": "No ds:Signature element found."}

    signed_info = _find_child(signature_el, "SignedInfo")
    signature_value_el = _find_child(signature_el, "SignatureValue")
    key_info = _find_child(signature_el, "KeyInfo")
    if signed_info is None or signature_value_el is None:
        return {
            "signature_valid": False,
            "error": "ds:Signature is missing SignedInfo or SignatureValue.",
        }

    cert = _extract_signer_cert(key_info) if key_info is not None else None
    if cert is None:
        return {
            "signature_valid": False,
            "error": "No X.509 certificate found in ds:KeyInfo to verify against.",
        }

    canon_method = _find_child(signed_info, "CanonicalizationMethod")
    canon_alg = canon_method.get("Algorithm") if canon_method is not None else _C14N_ALG

    reference = _find_child(signed_info, "Reference")
    if reference is None:
        return {"signature_valid": False, "error": "ds:SignedInfo has no ds:Reference."}

    digest_method = _find_child(reference, "DigestMethod")
    digest_value_el = _find_child(reference, "DigestValue")
    if digest_method is None or digest_value_el is None:
        return {
            "signature_valid": False,
            "error": "ds:Reference is missing DigestMethod/DigestValue.",
        }

    digest_alg = digest_method.get("Algorithm", "")
    digest_hash_cls = _DIGEST_HASH_NAMES.get(digest_alg)
    if digest_hash_cls is None:
        return {"signature_valid": False, "error": f"Unsupported digest algorithm: {digest_alg}"}

    # Enveloped-signature: recompute the digest over the document with the
    # ds:Signature element removed, canonicalized per the Reference's own
    # transform (falling back to SignedInfo's CanonicalizationMethod).
    transforms_alg = canon_alg
    transforms_el = _find_child(reference, "Transforms")
    if transforms_el is not None:
        for t in transforms_el:
            if _local(t.tag) == "Transform":
                alg = t.get("Algorithm", "")
                if alg in (_C14N_ALG, _EXC_C14N_ALG):
                    transforms_alg = alg

    doc_copy = etree.fromstring(etree.tostring(root))
    for el in list(doc_copy.iter()):
        if _local(el.tag) == "Signature" and el.tag.startswith(f"{{{_DS_NS}}}"):
            el.getparent().remove(el)
            break

    import base64  # noqa: PLC0415
    import hashlib  # noqa: PLC0415

    recomputed_digest = hashlib.new(
        digest_hash_cls().name, _c14n_for_algorithm(doc_copy, transforms_alg)
    ).digest()
    recomputed_digest_b64 = base64.b64encode(recomputed_digest).decode()
    if recomputed_digest_b64 != (digest_value_el.text or "").strip():
        return {"signature_valid": False, "error": "Reference digest mismatch."}

    signature_method = _find_child(signed_info, "SignatureMethod")
    sig_alg = signature_method.get("Algorithm", "") if signature_method is not None else ""
    sig_hash_cls = _SIGNATURE_HASH_NAMES.get(sig_alg)
    if sig_hash_cls is None:
        return {"signature_valid": False, "error": f"Unsupported signature algorithm: {sig_alg}"}

    signed_info_c14n = _c14n_for_algorithm(signed_info, canon_alg)
    signature_bytes = base64.b64decode((signature_value_el.text or "").strip())

    try:
        cert.public_key().verify(  # type: ignore[union-attr]
            signature_bytes, signed_info_c14n, padding.PKCS1v15(), sig_hash_cls()
        )
    except Exception as exc:  # noqa: BLE001 - InvalidSignature or key-type mismatch
        return {"signature_valid": False, "error": f"Signature verification failed: {exc}"}

    result: dict[str, Any] = {"signature_valid": True, "error": None}
    if environment is not None:
        result["chain"] = validate_certificate_chain(
            cert.public_bytes(serialization.Encoding.DER), environment
        )
    return result


def _find_child(parent: etree._Element, local_name: str) -> etree._Element | None:
    for el in parent:
        if _local(el.tag) == local_name:
            return el
    return None


def _extract_signer_cert(key_info: etree._Element) -> x509.Certificate | None:
    for el in key_info.iter():
        if _local(el.tag) == "X509Certificate":
            import base64  # noqa: PLC0415

            der = base64.b64decode((el.text or "").strip())
            return x509.load_der_x509_certificate(der)
    return None
