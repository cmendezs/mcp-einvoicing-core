"""EN 16931 semantic code-list tool plugin for mcp-einvoicing-core.

Mountable via ``EInvoicingMCPServer.register_plugin()``, matching the
``ToolRegistrationFn`` convention (see ``mcp_einvoicing_core.peppol.tools``
for the identical pattern applied to the OpenPeppol eDEC code lists).

Usage (country package)::

    from mcp_einvoicing_core.en16931_codelist_tools import register_en16931_codelist_tools

    mcp.register_plugin(register_en16931_codelist_tools, "en16931_codelists")

All tools require EINVOICING_EN16931_CODELIST_DIR to be set (a local,
deployer-supplied copy of the CEF EN 16931 code lists, not bundled with this
package). See ``mcp_einvoicing_core.en16931_codelists`` for why.
"""

from __future__ import annotations

from typing import Any

from mcp_einvoicing_core import en16931_codelists as codelists


def register_en16931_codelist_tools(mcp: Any) -> None:
    """Register the EN 16931 semantic code-list tool surface onto *mcp*.

    Args:
        mcp: A FastMCP instance (the `.mcp` attribute of an
            `EInvoicingMCPServer`, or a bare `FastMCP()`).

    Registers list_* / check_* pairs for: country, currency, ICD, UNCL1001
    (document name), UNCL1153 (reference qualifier), UNCL4461 (payment
    means), UNCL5305 (VAT category), allowance reason, item type, charge
    reason, MIME, EAS, VATEX — plus get_en16931_codelist_version.
    """

    def list_country_codes() -> dict[str, Any]:
        """List ISO 3166-1 alpha-2 country codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_country_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_country_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized ISO 3166-1 alpha-2 country code."""
        try:
            return {"configured": True, **codelists.check_country_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_currency_codes() -> dict[str, Any]:
        """List ISO 4217 currency codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_currency_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_currency_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized ISO 4217 currency code."""
        try:
            return {"configured": True, **codelists.check_currency_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_icd_codes() -> dict[str, Any]:
        """List ISO 6523 ICD codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_icd_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_icd_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized ISO 6523 ICD code."""
        try:
            return {"configured": True, **codelists.check_icd_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_document_name_codes() -> dict[str, Any]:
        """List UNCL1001 document name codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_document_name_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_document_name_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized UNCL1001 document name code."""
        try:
            return {"configured": True, **codelists.check_document_name_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_reference_qualifier_codes() -> dict[str, Any]:
        """List UNCL1153 reference qualifier codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_reference_qualifier_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_reference_qualifier_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized UNCL1153 reference qualifier code."""
        try:
            return {"configured": True, **codelists.check_reference_qualifier_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_payment_means_codes() -> dict[str, Any]:
        """List UNCL4461 payment means codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_payment_means_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_payment_means_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized UNCL4461 payment means code."""
        try:
            return {"configured": True, **codelists.check_payment_means_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_vat_category_codes() -> dict[str, Any]:
        """List UNCL5305 VAT category codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_vat_category_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_vat_category_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized UNCL5305 VAT category code."""
        try:
            return {"configured": True, **codelists.check_vat_category_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_allowance_reason_codes() -> dict[str, Any]:
        """List allowance reason codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_allowance_reason_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_allowance_reason_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized allowance reason code."""
        try:
            return {"configured": True, **codelists.check_allowance_reason_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_item_type_codes() -> dict[str, Any]:
        """List item type identification codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_item_type_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_item_type_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized item type identification code."""
        try:
            return {"configured": True, **codelists.check_item_type_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_charge_reason_codes() -> dict[str, Any]:
        """List charge reason codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_charge_reason_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_charge_reason_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized charge reason code."""
        try:
            return {"configured": True, **codelists.check_charge_reason_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_mime_codes() -> dict[str, Any]:
        """List recognized MIME types for embedded attachments."""
        try:
            return {"configured": True, "codes": codelists.list_mime_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_mime_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized MIME type for embedded attachments."""
        try:
            return {"configured": True, **codelists.check_mime_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_eas_codes() -> dict[str, Any]:
        """List Electronic Address Scheme (EAS) codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_eas_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_eas_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized Electronic Address Scheme code."""
        try:
            return {"configured": True, **codelists.check_eas_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def list_vatex_codes() -> dict[str, Any]:
        """List VATEX (VAT exemption reason) codes from the CEF EN 16931 code list."""
        try:
            return {"configured": True, "codes": codelists.list_vatex_codes()}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "codes": []}

    def check_vatex_code(code: str) -> dict[str, Any]:
        """Check whether *code* is a recognized VATEX VAT exemption reason code."""
        try:
            return {"configured": True, **codelists.check_vatex_code(code)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def get_en16931_codelist_version() -> dict[str, Any]:
        """Report the CEF EN 16931 code-list release version(s) currently configured locally."""
        return codelists.get_en16931_codelist_version()

    mcp.tool()(list_country_codes)
    mcp.tool()(check_country_code)
    mcp.tool()(list_currency_codes)
    mcp.tool()(check_currency_code)
    mcp.tool()(list_icd_codes)
    mcp.tool()(check_icd_code)
    mcp.tool()(list_document_name_codes)
    mcp.tool()(check_document_name_code)
    mcp.tool()(list_reference_qualifier_codes)
    mcp.tool()(check_reference_qualifier_code)
    mcp.tool()(list_payment_means_codes)
    mcp.tool()(check_payment_means_code)
    mcp.tool()(list_vat_category_codes)
    mcp.tool()(check_vat_category_code)
    mcp.tool()(list_allowance_reason_codes)
    mcp.tool()(check_allowance_reason_code)
    mcp.tool()(list_item_type_codes)
    mcp.tool()(check_item_type_code)
    mcp.tool()(list_charge_reason_codes)
    mcp.tool()(check_charge_reason_code)
    mcp.tool()(list_mime_codes)
    mcp.tool()(check_mime_code)
    mcp.tool()(list_eas_codes)
    mcp.tool()(check_eas_code)
    mcp.tool()(list_vatex_codes)
    mcp.tool()(check_vatex_code)
    mcp.tool()(get_en16931_codelist_version)
