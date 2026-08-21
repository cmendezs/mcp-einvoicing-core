"""Shared hybrid-PDF tool plugin for mcp-einvoicing-core.

Mountable via ``EInvoicingMCPServer.register_plugin()``, matching the
``ToolRegistrationFn`` convention in ``mcp_einvoicing_core.base_server``.
Wraps ``PDFEmbedder.identify()`` and ``PDFEmbedder.extract()`` as a single
FastMCP-native tool so country packages stop reimplementing their own
canonical-filename fallback loop (see CORE-PDF-EXTRACT-1, which absorbs
DE's ``_ZUGFERD_ATTACHMENT_FILENAMES`` loop in ``tools/invoice_parse.py``).

Usage (country package)::

    from mcp_einvoicing_core.pdf_tools import register_pdf_tools

    mcp.register_plugin(register_pdf_tools, "pdf")
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from mcp_einvoicing_core.pdf import PDFEmbedder

logger = logging.getLogger(__name__)


async def identify_and_extract_pdf(pdf_base64: str) -> dict[str, Any]:
    """Identify a hybrid PDF/A-3 invoice and extract its embedded XML.

    Reads XMP metadata to identify whether the file is a Factur-X/ZUGFeRD
    hybrid PDF (see `PDFEmbedder.identify`; the XMP schema itself is verified
    against a real sample, but a PDF from a different producer may not carry
    the same XMP shape), then extracts the embedded XML attachment by trying
    `CANONICAL_HYBRID_PDF_FILENAMES` in turn.

    Args:
        pdf_base64: Base64-encoded PDF/A-3 file bytes.

    Returns a dict with the `PDFEmbedder.identify()` fields
    (`is_hybrid_pdf`, `conformance_level`, `document_type`,
    `document_filename`, `version`) plus:
        matched_filename: the canonical attachment filename that was found,
            or None if no known hybrid filename matched.
        xml_base64: base64-encoded extracted XML, or None if not found.
    """
    pdf_bytes = base64.b64decode(pdf_base64)

    info: dict[str, Any] = dict(PDFEmbedder.identify(pdf_bytes))

    extracted = PDFEmbedder.extract(pdf_bytes, filename=None)
    if extracted is None:
        info["matched_filename"] = None
        info["xml_base64"] = None
    else:
        matched_filename, xml_bytes = extracted
        info["matched_filename"] = matched_filename
        info["xml_base64"] = base64.b64encode(xml_bytes).decode("ascii")

    return info


def register_pdf_tools(mcp: Any) -> None:
    """Register the shared hybrid-PDF tool surface onto *mcp*."""
    mcp.tool()(identify_and_extract_pdf)
