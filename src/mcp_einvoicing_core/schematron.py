"""Document validation ABCs and Schematron XSLT implementation.

Public API
----------
BaseStructuredValidator
    Abstract base class for all document validators. Extend this for any
    schema format: XSD, JSON Schema, CSV, SVRL, or proprietary rule engines.
    All implementations return ``ValidationResult`` so callers handle findings
    uniformly regardless of the underlying schema format.

ValidationMessage, ValidationResult
    Shared result types returned by every BaseStructuredValidator implementation.

SchematronValidator
    Concrete XSLT 1.0 / SVRL implementation for EN 16931, Peppol, XRechnung.
    Country packages subclass it and supply their own stylesheet path.

Usage in a country package:

    from mcp_einvoicing_core.schematron import SchematronValidator, ValidationResult

    _STYLESHEET_MAP: dict[str, Path] = {
        "en16931_cii": RESOURCES_DIR / "EN16931-CII-validation.xslt",
        "xrechnung_cii": RESOURCES_DIR / "XRechnung-CII-validation.xslt",
    }

    class DESchematronValidator(SchematronValidator):
        def __init__(self, stylesheet_key: str) -> None:
            path = _STYLESHEET_MAP.get(stylesheet_key)
            if path is None:
                raise ValueError(f"Unknown stylesheet key: {stylesheet_key!r}")
            super().__init__(path)

SVRL namespace: http://purl.oclc.org/dsdl/svrl
Skeleton Schematron: https://github.com/Schematron/schematron
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from mcp_einvoicing_core.xml_utils import safe_fromstring, safe_parser

logger = logging.getLogger(__name__)

_SVRL_NS = "http://purl.oclc.org/dsdl/svrl"
_SVRL_NSMAP = {"svrl": _SVRL_NS}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationMessage:
    """Single finding returned by a Schematron rule.

    severity: "error" | "fatal" | "warning" | "info"
    rule_id:  Rule identifier (e.g. "BR-DE-1", "BR-S-08", "PEPPOL-EN16931-R004")
    location: XPath expression locating the failing node in the source document
    text:     Human-readable failure message from <svrl:text>
    """

    severity: str
    rule_id: str
    location: str
    text: str


@dataclass
class ValidationResult:
    """Aggregated result of a full Schematron validation run.

    is_valid: True when no error-severity or fatal-severity findings were raised.
    profile:  Profile name / stylesheet key set by the caller (informational).
    syntax:   Syntax variant ("CII", "UBL", …) set by the caller (informational).
    """

    is_valid: bool
    errors: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)
    profile: str = ""
    syntax: str = ""

    def to_dict(self) -> dict:
        """Return a plain dict suitable for MCP tool responses."""
        return {
            "is_valid": self.is_valid,
            "profile": self.profile,
            "syntax": self.syntax,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [vars(e) for e in self.errors],
            "warnings": [vars(w) for w in self.warnings],
        }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseStructuredValidator(ABC):
    """Abstract base class for all document structure validators.

    Concrete implementations cover different schema and validation formats:

    - ``SchematronValidator`` — XSLT 1.0 Schematron / SVRL
      (EN 16931, Peppol BIS 3.0, XRechnung, PINT-*)
    - [Future] XSDValidator — XML Schema Definition
      (DE ZUGFeRD, IT FatturaPA, PL KSeF FA(3))
    - [Future] JSONSchemaValidator — JSON Schema Draft 2020-12
      (MY MyInvois, IN GSTN e-invoice, SA ZATCA Phase 2 clearance payload)
    - [Future] HybridValidator — JSON envelope + embedded XML
      (SA ZATCA UBL inside JSON, EG ETA)

    All implementations return ``ValidationResult`` so callers can handle
    findings uniformly regardless of the underlying schema format.

    The ``validate()`` contract requires that the method never raise —
    parsing failures and schema errors must be captured as findings inside
    the returned ``ValidationResult``.
    """

    @abstractmethod
    def validate(
        self,
        document: bytes,
        *,
        profile: str = "",
        syntax: str = "",
    ) -> ValidationResult:
        """Validate *document* bytes and return structured findings.

        Args:
            document: Raw document bytes (XML, JSON, or other format).
            profile: Profile label to embed in the result (e.g. ``"EN_16931"``).
                     Not used in validation logic — informational only.
            syntax:  Syntax variant label (e.g. ``"CII"``, ``"UBL"``, ``"JSON"``).
                     Not used in validation logic — informational only.

        Returns:
            ``ValidationResult`` with ``is_valid``, ``errors``, and ``warnings``.
            Never raises — XML/JSON parse errors appear as error-severity findings.
        """


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class SchematronValidator(BaseStructuredValidator):
    """Apply a Schematron XSLT stylesheet to an XML document and parse SVRL.

    The stylesheet must be a pre-compiled Skeleton Schematron XSLT 1.0 file.
    Stylesheets are loaded once on construction and reused for all calls to
    validate(), so construct one instance per stylesheet and keep it alive.

    validate() never raises — XML parse errors are captured as error-severity
    ValidationMessages so callers receive a uniform ValidationResult in all cases.

    Subclassing:
        Country packages typically subclass to add a stylesheet key map:

            class MyValidator(SchematronValidator):
                def __init__(self, key: str) -> None:
                    super().__init__(_MAP[key])

        They may also override _parse_svrl() to handle non-standard SVRL extensions.
    """

    def __init__(self, stylesheet_path: Path | str) -> None:
        """Load and compile a Schematron XSLT stylesheet.

        Args:
            stylesheet_path: Path to the pre-compiled XSLT stylesheet file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If lxml cannot parse the XSLT.
        """
        path = Path(stylesheet_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Schematron stylesheet not found: {path}. "
                "Run the package's download-rules command to fetch official artefacts."
            )
        try:
            self._transform = etree.XSLT(etree.parse(str(path), safe_parser(load_dtd=True)))
        except etree.XSLTParseError as exc:
            raise ValueError(
                f"Failed to parse Schematron stylesheet {path}: {exc}"
            ) from exc
        self._stylesheet_path = path

    def validate(self, xml_bytes: bytes, *, profile: str = "", syntax: str = "") -> ValidationResult:
        """Validate xml_bytes against the Schematron stylesheet.

        Args:
            xml_bytes: Raw XML document bytes (UTF-8 or with XML declaration).
            profile:   Profile label to embed in the returned ValidationResult
                       (e.g. "EN_16931").  Not used in validation logic.
            syntax:    Syntax label to embed in the result (e.g. "CII", "UBL").

        Returns:
            ValidationResult with is_valid, errors, warnings, profile, syntax.
            Never raises — XML parse errors appear as "error"-severity findings.
        """
        try:
            doc = safe_fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationMessage(
                        severity="error",
                        rule_id="XML-PARSE",
                        location="/",
                        text=str(exc),
                    )
                ],
                profile=profile,
                syntax=syntax,
            )

        svrl_doc = self._transform(doc)
        result = self._parse_svrl(svrl_doc)
        result.profile = profile
        result.syntax = syntax
        return result

    def _parse_svrl(self, svrl_doc: etree._XSLTResultTree) -> ValidationResult:
        """Parse SVRL output into a ValidationResult.

        Iterates <svrl:failed-assert> elements.  The flag attribute determines
        severity: "fatal" and "error" → errors list; everything else → warnings.

        Override in subclasses to handle non-standard SVRL extensions or
        additional element types (e.g. <svrl:successful-report>).
        """
        errors: list[ValidationMessage] = []
        warnings: list[ValidationMessage] = []

        for failed in svrl_doc.xpath("//svrl:failed-assert", namespaces=_SVRL_NSMAP):
            flag = (failed.get("flag") or "error").lower()
            rule_id = failed.get("id") or ""
            location = failed.get("location") or ""
            text_el = failed.find(f"{{{_SVRL_NS}}}text")
            text = (text_el.text or "").strip() if text_el is not None else ""

            msg = ValidationMessage(
                severity=flag, rule_id=rule_id, location=location, text=text
            )
            if flag in ("error", "fatal"):
                errors.append(msg)
            else:
                warnings.append(msg)

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# Abstract bases for non-Schematron validation families
# ---------------------------------------------------------------------------


class BaseXSDValidator(BaseStructuredValidator):
    """Abstract base for XML Schema Definition validators.

    Country packages subclass this for XSD-based format validation:
    ZUGFeRD (DE), FatturaPA (IT), KSeF FA(3) (PL), and any format
    that ships an official XSD rather than a Schematron ruleset.

    Implementors must supply a ``validate()`` method that parses the XSD
    once on construction and reuses it for all calls.

    Usage:
        class FatturaPAXSDValidator(BaseXSDValidator):
            def __init__(self, xsd_path: Path) -> None:
                self._schema = etree.XMLSchema(etree.parse(str(xsd_path), safe_parser()))

            def validate(self, document: bytes, *, profile: str = "", syntax: str = "") -> ValidationResult:
                ...
    """


class BaseJSONValidator(BaseStructuredValidator):
    """Abstract base for JSON Schema validators.

    Country packages subclass this for JSON-based e-invoicing formats:
    MyInvois (MY), GSTN e-invoice (IN), ZATCA Phase 2 (SA), ETA (EG),
    and any format whose canonical schema is expressed in JSON Schema.

    Implementors must supply a ``validate()`` method that loads the JSON
    Schema once on construction and reuses it for all calls.

    Usage:
        class ZATCAJSONValidator(BaseJSONValidator):
            def __init__(self, schema_path: Path) -> None:
                self._schema = json.loads(schema_path.read_text())

            def validate(self, document: bytes, *, profile: str = "", syntax: str = "") -> ValidationResult:
                ...
    """
