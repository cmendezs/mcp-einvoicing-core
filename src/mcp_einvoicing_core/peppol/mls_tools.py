"""Peppol MLS (Message Level Status) tool plugin for mcp-einvoicing-core.

Mountable via ``EInvoicingMCPServer.register_plugin()``, matching the
``ToolRegistrationFn`` convention (see ``mcp_einvoicing_core.peppol.tools``).

Usage (country package)::

    from mcp_einvoicing_core.peppol.mls_tools import register_peppol_mls_tools

    mcp.register_plugin(register_peppol_mls_tools, "peppol_mls")

Requires the ``[xslt2]`` optional extra (``saxonche``) — the bundled MLS
Schematron stylesheet is XSLT 2.0.
"""

from __future__ import annotations

import base64
from typing import Any

from mcp_einvoicing_core.peppol.mls import (
    MLSDocumentReference,
    MLSDocumentResponse,
    MLSEndpoint,
    MLSResponse,
    MLSStatus,
    build_mls,
    validate_mls,
)


def register_peppol_mls_tools(mcp: Any) -> None:
    """Register the Peppol MLS tool surface onto *mcp*.

    Args:
        mcp: A FastMCP instance (the `.mcp` attribute of an
            `EInvoicingMCPServer`, or a bare `FastMCP()`).

    Registers:
        validate_mls_message: Schematron validation of an MLS document.
        build_mls_message:    Build a document-level (non-itemized) MLS
                               response — the common C3-responder case.
    """

    def validate_mls_message(mls_xml_base64: str) -> dict[str, Any]:
        """Validate a Peppol Message Level Status (MLS) document.

        Runs the bundled MLS Schematron rules (requires the ``[xslt2]``
        optional extra). No bespoke MLS XSD exists — full UBL 2.1 XSD
        validation is out of scope.

        Args:
            mls_xml_base64: Base64-encoded MLS (UBL ApplicationResponse-2) XML.
        """
        xml_bytes = base64.b64decode(mls_xml_base64)
        return validate_mls(xml_bytes).to_dict()

    def build_mls_message(
        mls_id: str,
        issue_date: str,
        sender_scheme_id: str,
        sender_value: str,
        receiver_scheme_id: str,
        receiver_value: str,
        document_reference_id: str,
        response_code: str,
        issue_time: str = "",
        description: str = "",
        status_reason_code: str = "",
    ) -> dict[str, Any]:
        """Build a document-level MLS response and return it base64-encoded.

        For per-line responses, build the document directly with
        `mcp_einvoicing_core.peppol.mls.build_mls`.

        Args:
            mls_id: The ``cbc:ID`` of this MLS document.
            issue_date: ISO date string, e.g. "2026-08-23".
            sender_scheme_id: ICD scheme of the sending Access Point's endpoint.
            sender_value: Sending Access Point's endpoint value.
            receiver_scheme_id: ICD scheme of the receiving endpoint (normally
                the original message's SBDH ``MLS_TO`` scheme).
            receiver_value: Receiving endpoint value.
            document_reference_id: The SBDH ``InstanceIdentifier`` of the
                source message this MLS reports on.
            response_code: "AB" (Acknowledged), "AP" (Accepted), or
                "RE" (Rejected).
            issue_time: Optional ISO time string, e.g. "12:00:00Z".
            description: Optional human-readable response text.
            status_reason_code: Optional: "SV", "BV", "BW", or "FD"
                (required by the Schematron when response_code is "RE").
        """
        status = MLSStatus(reason_code=status_reason_code) if status_reason_code else None
        document_response = MLSDocumentResponse(
            response=MLSResponse(
                response_code=response_code, description=description or None, status=status
            ),
            document_reference=MLSDocumentReference(id=document_reference_id),
        )
        xml_bytes = build_mls(
            mls_id=mls_id,
            issue_date=issue_date,
            issue_time=issue_time or None,
            sender=MLSEndpoint(scheme_id=sender_scheme_id, value=sender_value),
            receiver=MLSEndpoint(scheme_id=receiver_scheme_id, value=receiver_value),
            document_response=document_response,
        )
        return {"mls_xml_base64": base64.b64encode(xml_bytes).decode()}

    mcp.tool()(validate_mls_message)
    mcp.tool()(build_mls_message)
