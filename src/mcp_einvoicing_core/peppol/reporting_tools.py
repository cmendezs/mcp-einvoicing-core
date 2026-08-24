"""Peppol EUSR/TSR reporting tool plugin for mcp-einvoicing-core.

Mountable via ``EInvoicingMCPServer.register_plugin()``, matching the
``ToolRegistrationFn`` convention (see ``mcp_einvoicing_core.peppol.tools``).

Usage (country package)::

    from mcp_einvoicing_core.peppol.reporting_tools import register_peppol_reporting_tools

    mcp.register_plugin(register_peppol_reporting_tools, "peppol_reporting")

Both tools require the ``[xslt2]`` optional extra (``saxonche``) — the
bundled EUSR/TSR Schematron stylesheets are XSLT 2.0.
"""

from __future__ import annotations

import base64
from typing import Any

from mcp_einvoicing_core.peppol.reporting import validate_eusr, validate_tsr


def register_peppol_reporting_tools(mcp: Any) -> None:
    """Register the Peppol EUSR/TSR reporting tool surface onto *mcp*.

    Args:
        mcp: A FastMCP instance (the `.mcp` attribute of an
            `EInvoicingMCPServer`, or a bare `FastMCP()`).

    Registers:
        validate_eusr_report: XSD + Schematron validation of an EUSR document.
        validate_tsr_report:  XSD + Schematron validation of a TSR document.
    """

    def validate_eusr_report(report_xml_base64: str) -> dict[str, Any]:
        """Validate a Peppol End User Statistics Report (EUSR) document.

        Runs XSD structural validation, then Schematron business rules
        (requires the ``[xslt2]`` optional extra).

        Args:
            report_xml_base64: Base64-encoded EUSR XML document.
        """
        xml_bytes = base64.b64decode(report_xml_base64)
        return validate_eusr(xml_bytes).to_dict()

    def validate_tsr_report(report_xml_base64: str) -> dict[str, Any]:
        """Validate a Peppol Transaction Statistics Report (TSR) document.

        Runs XSD structural validation, then Schematron business rules
        (requires the ``[xslt2]`` optional extra).

        Args:
            report_xml_base64: Base64-encoded TSR XML document.
        """
        xml_bytes = base64.b64decode(report_xml_base64)
        return validate_tsr(xml_bytes).to_dict()

    mcp.tool()(validate_eusr_report)
    mcp.tool()(validate_tsr_report)
