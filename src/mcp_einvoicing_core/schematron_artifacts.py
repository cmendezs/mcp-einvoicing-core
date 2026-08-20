"""Bundled, pre-compiled Schematron artefacts shipped by mcp-einvoicing-core.

Unlike ``schematron.py`` (the generic XSLT 1.0/2.0+ SVRL *engine*, stylesheet
path supplied by the caller), this module ships a specific, ready-to-use
*artefact*: the compiled CEN EN 16931 base Schematron (the ``BR-*`` rules
shared by every EN 16931 CIUS — Peppol BIS 3.0, XRechnung, Factur-X, etc.).

Scope: EN 16931 base rules only. Does **not** include the Peppol-specific
overlay (``PEPPOL-EN16931-UBL-*.sch``) — that file has no confirmed
redistribution rights and is not compiled or bundled anywhere in this
package. A document that passes ``en16931_base_schematron_validator()``
has not been checked against Peppol network-interoperability rules
(profile/process ID registration, ``EndpointID`` scheme constraints,
narrowed code lists) and may still be rejected by a real Peppol Access
Point. Callers must label results accordingly (e.g. a
``scope="en16931-base-only"`` key in their own tool response metadata) and
must never present this as full Peppol BIS3 conformance.

Full licensing investigation and decision:
context-library/decisions/peppol-schematron-artifact.md (root repo).
Compiled-artefact provenance (source .sch, compiler, retrieved dates):
specs/peppol/README.md.

Usage:

    from mcp_einvoicing_core.schematron_artifacts import en16931_base_schematron_validator

    validator = en16931_base_schematron_validator()
    result = validator.validate(xml_bytes, profile="peppol-bis-3", syntax="UBL")
"""

from __future__ import annotations

from pathlib import Path

from mcp_einvoicing_core.schematron import BaseStructuredValidator, load_schematron_validator

_RESOURCES_DIR = Path(__file__).parent / "resources" / "schematron"
_EN16931_BASE_XSLT = _RESOURCES_DIR / "en16931_base" / "CEN-EN16931-UBL.xslt"


def en16931_base_schematron_validator() -> BaseStructuredValidator:
    """Return a validator for the CEN EN 16931 base Schematron (``BR-*`` rules).

    Compiled from the vendored ``CEN-EN16931-UBL-3.0.20.sch`` (EUPL 1.2) via
    SchXslt2; bundled inside the wheel so no compile step runs at install or
    call time. Backed by ``SaxonSchematronValidator`` (XSLT 3.0, via the
    optional ``[xslt2]`` extra) since the compiled stylesheet targets XSLT 3.0.

    Returns:
        A ``BaseStructuredValidator`` ready to call ``.validate(xml_bytes, ...)``.

    Raises:
        FileNotFoundError: If the bundled artefact is missing — should not
            happen in an installed wheel; indicates a packaging regression.
        ImportError: If the optional ``saxonche`` extra is not installed.
    """
    return load_schematron_validator(_EN16931_BASE_XSLT)
