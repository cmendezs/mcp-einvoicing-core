"""Tests for PDFEmbedder.extract() canonical-name fallback and identify()
(CORE-PDF-EXTRACT-1). asyncio_mode = "auto" (pyproject.toml).
"""

from __future__ import annotations

import base64
import io

import pikepdf
import pytest

from mcp_einvoicing_core.pdf import CANONICAL_HYBRID_PDF_FILENAMES, PDFEmbedder

_SAMPLE_XML = b"<Invoice><ID>INV-001</ID></Invoice>"


def _blank_pdf_bytes() -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page()
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


class TestExtractExplicitFilenameUnchanged:
    """Backward compatibility: explicit filename= keeps returning bytes|None."""

    def test_returns_bytes_on_match(self) -> None:
        hybrid = PDFEmbedder.embed(_blank_pdf_bytes(), _SAMPLE_XML, filename="factur-x.xml")
        result = PDFEmbedder.extract(hybrid, filename="factur-x.xml")
        assert result == _SAMPLE_XML

    def test_returns_none_on_miss(self) -> None:
        hybrid = PDFEmbedder.embed(_blank_pdf_bytes(), _SAMPLE_XML, filename="factur-x.xml")
        result = PDFEmbedder.extract(hybrid, filename="wrong-name.xml")
        assert result is None

    def test_default_filename_unchanged(self) -> None:
        hybrid = PDFEmbedder.embed(_blank_pdf_bytes(), _SAMPLE_XML, filename="factur-x.xml")
        result = PDFEmbedder.extract(hybrid)
        assert result == _SAMPLE_XML


class TestExtractCanonicalFallback:
    @pytest.mark.parametrize("canonical_name", CANONICAL_HYBRID_PDF_FILENAMES)
    def test_finds_each_canonical_filename(self, canonical_name: str) -> None:
        hybrid = PDFEmbedder.embed(_blank_pdf_bytes(), _SAMPLE_XML, filename=canonical_name)
        result = PDFEmbedder.extract(hybrid, filename=None)
        assert result == (canonical_name, _SAMPLE_XML)

    def test_returns_none_when_no_canonical_name_present(self) -> None:
        hybrid = PDFEmbedder.embed(_blank_pdf_bytes(), _SAMPLE_XML, filename="something-else.xml")
        result = PDFEmbedder.extract(hybrid, filename=None)
        assert result is None

    def test_finds_non_first_canonical_name(self) -> None:
        # Embed under the second canonical name; the fallback must still find
        # it even though the first candidate (factur-x.xml) is absent.
        second = CANONICAL_HYBRID_PDF_FILENAMES[1]
        hybrid = PDFEmbedder.embed(_blank_pdf_bytes(), _SAMPLE_XML, filename=second)
        result = PDFEmbedder.extract(hybrid, filename=None)
        assert result == (second, _SAMPLE_XML)


class TestCanonicalFilenameOrder:
    def test_spec_confirmed_names_precede_legacy_names(self) -> None:
        # factur-x.xml / xrechnung.xml are confirmed against the "Filename"
        # codelist; the ZUGFeRD 1.x legacy names must be tried only after.
        assert CANONICAL_HYBRID_PDF_FILENAMES[:2] == ("factur-x.xml", "xrechnung.xml")
        assert set(CANONICAL_HYBRID_PDF_FILENAMES[2:]) == {
            "ZUGFeRD-invoice.xml",
            "zugferd-invoice.xml",
        }


class TestEmbedWritesExtensionSchemaDeclaration:
    """embed() must write both the pdfaExtension:schemas declaration block
    and the fx:* value block -- a real Factur-X XMP requires both (see the
    module docstring); previously only the fx:* block was written."""

    def _xmp_str(self, hybrid_pdf_bytes: bytes) -> str:
        with pikepdf.open(io.BytesIO(hybrid_pdf_bytes)) as pdf:
            return bytes(pdf.Root["/Metadata"].read_bytes()).decode("utf-8")

    def test_extension_schema_block_present(self) -> None:
        hybrid = PDFEmbedder.embed(
            _blank_pdf_bytes(), _SAMPLE_XML, filename="factur-x.xml", xmp_profile="EN 16931"
        )
        xmp = self._xmp_str(hybrid)
        assert "pdfaExtension:schemas" in xmp
        assert (
            "<pdfaSchema:namespaceURI>urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#</pdfaSchema:namespaceURI>"
            in xmp
        )
        assert "<pdfaSchema:prefix>fx</pdfaSchema:prefix>" in xmp

    def test_identify_still_finds_fx_fields_with_both_blocks_present(self) -> None:
        # Regression test: the extension-schema block also contains the fx:
        # namespace URI as plain text, which could cause identify() to match
        # the wrong <rdf:Description> block and report no fields found.
        hybrid = PDFEmbedder.embed(
            _blank_pdf_bytes(), _SAMPLE_XML, filename="xrechnung.xml", xmp_profile="XRECHNUNG"
        )
        info = PDFEmbedder.identify(hybrid)
        assert info["is_hybrid_pdf"] is True
        assert info["conformance_level"] == "XRECHNUNG"
        assert info["document_filename"] == "xrechnung.xml"


class TestIdentify:
    def test_reports_not_hybrid_when_no_xmp_profile_set(self) -> None:
        hybrid = PDFEmbedder.embed(_blank_pdf_bytes(), _SAMPLE_XML, filename="factur-x.xml")
        info = PDFEmbedder.identify(hybrid)
        assert info["is_hybrid_pdf"] is False

    def test_reports_hybrid_and_fields_when_xmp_profile_set(self) -> None:
        hybrid = PDFEmbedder.embed(
            _blank_pdf_bytes(),
            _SAMPLE_XML,
            filename="factur-x.xml",
            xmp_profile="EN 16931",
        )
        info = PDFEmbedder.identify(hybrid)
        assert info["is_hybrid_pdf"] is True
        assert info["conformance_level"] == "EN 16931"
        assert info["document_filename"] == "factur-x.xml"
        assert info["document_type"] == "INVOICE"
        assert info["version"] == "1.0"

    def test_reports_not_hybrid_for_plain_pdf(self) -> None:
        info = PDFEmbedder.identify(_blank_pdf_bytes())
        assert info["is_hybrid_pdf"] is False
        assert info["conformance_level"] is None


class TestIdentifyAndExtractPdfTool:
    async def test_tool_combines_identify_and_extract(self) -> None:
        from mcp_einvoicing_core.pdf_tools import identify_and_extract_pdf

        hybrid = PDFEmbedder.embed(
            _blank_pdf_bytes(),
            _SAMPLE_XML,
            filename="xrechnung.xml",
            xmp_profile="XRECHNUNG",
        )
        result = await identify_and_extract_pdf(base64.b64encode(hybrid).decode("ascii"))
        assert result["is_hybrid_pdf"] is True
        assert result["matched_filename"] == "xrechnung.xml"
        assert base64.b64decode(result["xml_base64"]) == _SAMPLE_XML

    async def test_tool_reports_no_match_for_plain_pdf(self) -> None:
        from mcp_einvoicing_core.pdf_tools import identify_and_extract_pdf

        result = await identify_and_extract_pdf(
            base64.b64encode(_blank_pdf_bytes()).decode("ascii")
        )
        assert result["is_hybrid_pdf"] is False
        assert result["matched_filename"] is None
        assert result["xml_base64"] is None
