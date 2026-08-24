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

SaxonSchematronValidator
    Concrete XSLT 2.0/3.0 / SVRL implementation backed by Saxon-HE (``saxonche``,
    optional extra: ``mcp-einvoicing-core[xslt2]``). Some Schematron-derived
    stylesheets (notably the FNFE-MPE Factur-X 1.08 / ZUGFeRD rules) use XPath
    2.0 constructs (``every ... satisfies``, ``string-join``, ``cast as``) that
    ``lxml``/``libxslt`` (XSLT 1.0 only) cannot compile — this is the gap
    tracked as DE-XSLT2-1 / FR-XSLT2-1 in context-library/audit-history.md.

get_xslt_version, load_schematron_validator
    ``get_xslt_version()`` reads the ``version`` attribute off a stylesheet's
    root element. ``load_schematron_validator()`` uses it to auto-dispatch to
    ``SchematronValidator`` (1.x) or ``SaxonSchematronValidator`` (2.x/3.x+).
    Country packages keep their own stylesheet-key → path map and call this
    factory with the resolved path — core does not know about country-specific
    keys.

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

Auto-dispatch usage (XSLT 1.0 and 2.0+ stylesheets in the same map):

    from mcp_einvoicing_core.schematron import load_schematron_validator

    def get_validator(stylesheet_key: str) -> BaseStructuredValidator:
        path = _STYLESHEET_MAP[stylesheet_key]
        return load_schematron_validator(path)

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
    - ``SaxonSchematronValidator`` — XSLT 2.0/3.0 Schematron / SVRL, via Saxon-HE
      (FNFE-MPE Factur-X 1.08 / ZUGFeRD; optional ``[xslt2]`` extra)
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
            raise ValueError(f"Failed to parse Schematron stylesheet {path}: {exc}") from exc
        self._stylesheet_path = path

    def validate(
        self, xml_bytes: bytes, *, profile: str = "", syntax: str = ""
    ) -> ValidationResult:
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
        return _extract_svrl_findings(svrl_doc)


def _extract_svrl_findings(svrl_root: etree._Element) -> ValidationResult:
    """Shared SVRL-to-ValidationResult logic used by every XSLT backend.

    Iterates <svrl:failed-assert> elements. The flag attribute determines
    severity: "fatal" and "error" → errors list; everything else → warnings.
    """
    errors: list[ValidationMessage] = []
    warnings: list[ValidationMessage] = []

    for failed in svrl_root.xpath("//svrl:failed-assert", namespaces=_SVRL_NSMAP):
        flag = (failed.get("flag") or "error").lower()
        rule_id = failed.get("id") or ""
        location = failed.get("location") or ""
        text_el = failed.find(f"{{{_SVRL_NS}}}text")
        text = (text_el.text or "").strip() if text_el is not None else ""

        msg = ValidationMessage(severity=flag, rule_id=rule_id, location=location, text=text)
        if flag in ("error", "fatal"):
            errors.append(msg)
        else:
            warnings.append(msg)

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def _parse_svrl_text(svrl_text: str) -> ValidationResult:
    """Parse SVRL XML text (as returned by a string-based XSLT engine) into a ValidationResult."""
    if not svrl_text.strip():
        return ValidationResult(is_valid=True)

    try:
        svrl_root = etree.fromstring(svrl_text.encode("utf-8"), safe_parser())
    except etree.XMLSyntaxError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationMessage(
                    severity="error", rule_id="SVRL-PARSE", location="/", text=str(exc)
                )
            ],
        )

    return _extract_svrl_findings(svrl_root)


# ---------------------------------------------------------------------------
# XSLT 2.0/3.0 backend (Saxon-HE via saxonche) — DE-XSLT2-1 / FR-XSLT2-1
# ---------------------------------------------------------------------------


def get_xslt_version(stylesheet_path: Path | str) -> str:
    """Return the ``version`` attribute on an XSLT stylesheet's root element.

    Defaults to ``"1.0"`` when the file cannot be read or the attribute is
    absent, matching XSLT's own default-version behaviour.
    """
    try:
        root = etree.parse(str(stylesheet_path), safe_parser()).getroot()
    except (OSError, etree.XMLSyntaxError) as exc:
        logger.warning("Could not read XSLT version from %s: %s", stylesheet_path, exc)
        return "1.0"
    return root.get("version") or "1.0"


class SaxonSchematronValidator(BaseStructuredValidator):
    """XSLT 2.0/3.0 Schematron validator backed by Saxon-HE via ``saxonche``.

    Use this for Schematron-derived stylesheets that use XPath 2.0+ constructs
    (``every ... satisfies``, ``string-join``, ``cast as``) which ``lxml``/
    ``libxslt`` (XSLT 1.0 only) cannot compile — e.g. the FNFE-MPE Factur-X
    1.08 / ZUGFeRD rule sets (DE-XSLT2-1, FR-XSLT2-1).

    Requires the optional ``saxonche`` extra:
        pip install mcp-einvoicing-core[xslt2]

    The import is deferred to construction so that packages which never need
    XSLT 2.0 validation do not need ``saxonche`` installed.
    """

    def __init__(self, stylesheet_path: Path | str) -> None:
        """Load and compile an XSLT 2.0/3.0 Schematron stylesheet.

        Args:
            stylesheet_path: Path to the pre-compiled XSLT stylesheet file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ImportError: If ``saxonche`` is not installed.
            ValueError: If Saxon cannot compile the stylesheet.
        """
        path = Path(stylesheet_path)
        if not path.exists():
            raise FileNotFoundError(f"Schematron stylesheet not found: {path}.")

        try:
            from saxonche import PySaxonProcessor  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                f"Stylesheet {path.name} requires XSLT 2.0/3.0 support (Saxon-HE). "
                "Install the optional extra with: pip install mcp-einvoicing-core[xslt2]"
            ) from exc

        # PySaxonProcessor is created once per validator; it holds the compiled
        # XSLT executable, which is reused across validate() calls.
        self._proc = PySaxonProcessor(license=False)
        xslt_processor = self._proc.new_xslt30_processor()
        try:
            self._executable = xslt_processor.compile_stylesheet(stylesheet_file=str(path))
        except Exception as exc:
            raise ValueError(f"Failed to compile XSLT stylesheet {path}: {exc}") from exc
        if self._executable is None:
            raise ValueError(f"Saxon returned no compiled executable for stylesheet {path}.")
        self._stylesheet_path = path

    def validate(self, document: bytes, *, profile: str = "", syntax: str = "") -> ValidationResult:
        """Validate document bytes against the compiled XSLT 2.0/3.0 stylesheet.

        Never raises — XML parse errors and Saxon transform errors are
        captured as error-severity ValidationMessages.
        """
        try:
            # utf-8-sig strips a leading UTF-8 BOM if present (several real-world
            # Factur-X/ZUGFeRD samples carry one); it is a no-op otherwise. A raw
            # "utf-8" decode leaves the BOM character in the string, which Saxon's
            # parse_xml(xml_text=...) rejects as "content not allowed in prolog".
            xdm_input = self._proc.parse_xml(xml_text=document.decode("utf-8-sig"))
        except Exception as exc:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationMessage(
                        severity="error", rule_id="XML-PARSE", location="/", text=str(exc)
                    )
                ],
                profile=profile,
                syntax=syntax,
            )

        try:
            svrl_text = self._executable.transform_to_string(xdm_node=xdm_input)
        except Exception as exc:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationMessage(
                        severity="error",
                        rule_id="XSLT-RUNTIME",
                        location="/",
                        text=f"Saxon XSLT transform failed: {exc}",
                    )
                ],
                profile=profile,
                syntax=syntax,
            )

        result = _parse_svrl_text(svrl_text or "")
        result.profile = profile
        result.syntax = syntax
        return result


def load_schematron_validator(stylesheet_path: Path | str) -> BaseStructuredValidator:
    """Return the right Schematron backend for *stylesheet_path*, auto-detected.

    Reads the ``version`` attribute on the XSLT root and dispatches to
    ``SchematronValidator`` (XSLT 1.0, via lxml/libxslt) for ``version="1.x"``,
    or ``SaxonSchematronValidator`` (XSLT 2.0+, via Saxon-HE) otherwise.

    Country packages keep their own stylesheet-key → path map; this factory
    only needs the resolved path.

    Raises:
        FileNotFoundError: If the stylesheet file does not exist.
        ImportError: If an XSLT 2.0+ stylesheet is requested without the
            optional ``saxonche`` extra installed.
        ValueError: If the stylesheet cannot be compiled by either backend.
    """
    version = get_xslt_version(stylesheet_path)
    if version.startswith("1."):
        return SchematronValidator(stylesheet_path)
    return SaxonSchematronValidator(stylesheet_path)


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


class XSDValidator(BaseXSDValidator):
    """Generic concrete XSD validator: loads one schema, validates any document.

    For formats that need only stock XML Schema validation with no
    format-specific behaviour (e.g. no multi-schema resolution). Country
    packages with more elaborate needs (schema sets that reference each
    other, custom error mapping) should still subclass `BaseXSDValidator`
    directly, as documented above.

    Usage:
        validator = XSDValidator(RESOURCES_DIR / "my-format.xsd")
        result = validator.validate(xml_bytes, profile="my-format")
    """

    def __init__(self, xsd_path: Path | str) -> None:
        """Load and compile an XSD schema.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If lxml cannot parse the XSD.
        """
        path = Path(xsd_path)
        if not path.exists():
            raise FileNotFoundError(f"XSD schema not found: {path}.")
        try:
            self._schema = etree.XMLSchema(etree.parse(str(path), safe_parser(load_dtd=True)))
        except etree.XMLSchemaParseError as exc:
            raise ValueError(f"Failed to parse XSD schema {path}: {exc}") from exc
        self._xsd_path = path

    def validate(self, document: bytes, *, profile: str = "", syntax: str = "") -> ValidationResult:
        """Validate *document* bytes against the XSD schema.

        Never raises — XML parse errors and schema violations both appear
        as error-severity `ValidationMessage`s.
        """
        try:
            doc = safe_fromstring(document)
        except etree.XMLSyntaxError as exc:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationMessage(
                        severity="error", rule_id="XML-PARSE", location="/", text=str(exc)
                    )
                ],
                profile=profile,
                syntax=syntax,
            )

        if self._schema.validate(doc):
            return ValidationResult(is_valid=True, profile=profile, syntax=syntax)

        errors = [
            ValidationMessage(
                severity="error",
                rule_id="XSD",
                location=f"line {entry.line}",
                text=entry.message,
            )
            for entry in self._schema.error_log
        ]
        return ValidationResult(is_valid=False, errors=errors, profile=profile, syntax=syntax)


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
