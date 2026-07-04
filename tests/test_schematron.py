"""Tests for mcp_einvoicing_core.schematron: XSLT 1.0 and XSLT 2.0/3.0 backends.

Covers:
  - SchematronValidator (XSLT 1.0, lxml/libxslt) — existing backend
  - get_xslt_version — reads the version attribute off a stylesheet's root
  - SaxonSchematronValidator (XSLT 2.0/3.0, Saxon-HE via saxonche) — DE-XSLT2-1 / FR-XSLT2-1
  - load_schematron_validator — auto-dispatch factory
"""

from __future__ import annotations

import importlib.util

import pytest

from mcp_einvoicing_core.schematron import (
    SaxonSchematronValidator,
    SchematronValidator,
    ValidationResult,
    get_xslt_version,
    load_schematron_validator,
)

_SAXON_AVAILABLE = importlib.util.find_spec("saxonche") is not None

# A minimal Skeleton-Schematron-style XSLT 1.0 stylesheet: flags any
# <invoice> element missing a <total> child as a failed-assert.
_XSLT1_STYLESHEET = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                 xmlns:svrl="http://purl.oclc.org/dsdl/svrl"
                 version="1.0">
  <xsl:output method="xml"/>
  <xsl:template match="/">
    <svrl:schematron-output>
      <xsl:if test="not(/invoice/total)">
        <svrl:failed-assert id="BR-TOTAL-1" location="/invoice" flag="error">
          <svrl:text>Missing total element</svrl:text>
        </svrl:failed-assert>
      </xsl:if>
    </svrl:schematron-output>
  </xsl:template>
</xsl:stylesheet>
"""

# The same rule, but expressed with an XPath 2.0 construct (`every ... satisfies`)
# that lxml/libxslt cannot compile — this is the shape of the real FeRD/Factur-X
# stylesheets that motivated DE-XSLT2-1 / FR-XSLT2-1.
_XSLT2_STYLESHEET = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                 xmlns:svrl="http://purl.oclc.org/dsdl/svrl"
                 version="2.0">
  <xsl:output method="xml"/>
  <xsl:template match="/">
    <svrl:schematron-output>
      <xsl:if test="not(/invoice/total) or not(every $t in /invoice/total satisfies string-length($t) gt 0)">
        <svrl:failed-assert id="BR-TOTAL-1" location="/invoice" flag="error">
          <svrl:text>Missing or empty total element</svrl:text>
        </svrl:failed-assert>
      </xsl:if>
    </svrl:schematron-output>
  </xsl:template>
</xsl:stylesheet>
"""

_VALID_INVOICE = b"<invoice><total>100.00</total></invoice>"
_INVALID_INVOICE = b"<invoice></invoice>"


@pytest.fixture
def xslt1_path(tmp_path):
    path = tmp_path / "xslt1.xslt"
    path.write_text(_XSLT1_STYLESHEET)
    return path


@pytest.fixture
def xslt2_path(tmp_path):
    path = tmp_path / "xslt2.xslt"
    path.write_text(_XSLT2_STYLESHEET)
    return path


class TestGetXsltVersion:
    def test_detects_xslt1(self, xslt1_path):
        assert get_xslt_version(xslt1_path) == "1.0"

    def test_detects_xslt2(self, xslt2_path):
        assert get_xslt_version(xslt2_path) == "2.0"

    def test_defaults_to_1_0_when_file_missing(self, tmp_path):
        assert get_xslt_version(tmp_path / "does-not-exist.xslt") == "1.0"


class TestSchematronValidatorXslt1:
    def test_valid_document(self, xslt1_path):
        validator = SchematronValidator(xslt1_path)
        result = validator.validate(_VALID_INVOICE, profile="TEST", syntax="XML")
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_document(self, xslt1_path):
        validator = SchematronValidator(xslt1_path)
        result = validator.validate(_INVALID_INVOICE)
        assert result.is_valid is False
        assert result.errors[0].rule_id == "BR-TOTAL-1"

    def test_rejects_xslt2_stylesheet(self, xslt2_path):
        """This is the DE-XSLT2-1 / FR-XSLT2-1 gap: lxml/libxslt cannot compile
        stylesheets that use XPath 2.0 constructs, even when only version="2.0"
        is declared without exotic functions in some cases; here the `every
        ... satisfies` construct guarantees a ValueError from the 1.0 backend."""
        with pytest.raises(ValueError):
            SchematronValidator(xslt2_path)


@pytest.mark.skipif(not _SAXON_AVAILABLE, reason="saxonche extra not installed")
class TestSaxonSchematronValidator:
    def test_valid_document(self, xslt2_path):
        validator = SaxonSchematronValidator(xslt2_path)
        result = validator.validate(_VALID_INVOICE, profile="TEST", syntax="XML")
        assert result.is_valid is True
        assert result.errors == []
        assert result.profile == "TEST"

    def test_invalid_document(self, xslt2_path):
        validator = SaxonSchematronValidator(xslt2_path)
        result = validator.validate(_INVALID_INVOICE)
        assert result.is_valid is False
        assert result.errors[0].rule_id == "BR-TOTAL-1"

    def test_also_handles_xslt1_stylesheet(self, xslt1_path):
        """Saxon is a superset engine — it can run XSLT 1.0 stylesheets too."""
        validator = SaxonSchematronValidator(xslt1_path)
        result = validator.validate(_VALID_INVOICE)
        assert result.is_valid is True

    def test_strips_utf8_bom(self, xslt2_path):
        """Several real-world Factur-X/ZUGFeRD worked examples carry a UTF-8 BOM.
        A raw "utf-8" decode leaves it in the string and Saxon's parse_xml
        rejects it as "content not allowed in prolog" — regression guard."""
        validator = SaxonSchematronValidator(xslt2_path)
        bom_prefixed = b"\xef\xbb\xbf" + _VALID_INVOICE
        result = validator.validate(bom_prefixed)
        assert result.is_valid is True
        assert result.errors == []

    def test_missing_stylesheet_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SaxonSchematronValidator(tmp_path / "missing.xslt")

    def test_malformed_xml_document_does_not_raise(self, xslt2_path):
        validator = SaxonSchematronValidator(xslt2_path)
        result = validator.validate(b"<not-well-formed")
        assert result.is_valid is False
        assert result.errors[0].rule_id == "XML-PARSE"


class TestSaxonUnavailable:
    def test_clear_import_error_without_saxonche(self, xslt2_path, monkeypatch):
        """Simulate the optional extra not being installed."""
        import sys

        monkeypatch.setitem(sys.modules, "saxonche", None)
        with pytest.raises(ImportError, match="mcp-einvoicing-core\\[xslt2\\]"):
            SaxonSchematronValidator(xslt2_path)


class TestLoadSchematronValidator:
    def test_dispatches_to_xslt1_backend(self, xslt1_path):
        validator = load_schematron_validator(xslt1_path)
        assert isinstance(validator, SchematronValidator)

    @pytest.mark.skipif(not _SAXON_AVAILABLE, reason="saxonche extra not installed")
    def test_dispatches_to_saxon_backend(self, xslt2_path):
        validator = load_schematron_validator(xslt2_path)
        assert isinstance(validator, SaxonSchematronValidator)
