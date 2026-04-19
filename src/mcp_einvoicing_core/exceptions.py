"""
Shared exception hierarchy for mcp-einvoicing-core.

All country adapters raise subclasses of EInvoicingError so the base server
can catch them uniformly and return a consistent {"error": "..."} dict to the MCP client.

Design philosophy:
- Every exception carries a human-readable message in English.
- Subclasses add structured data (e.g. error list for XSD, HTTP status for platform).
- Country adapters never raise raw httpx / lxml errors to MCP tools; they catch those
  and re-raise as EInvoicingError subclasses.
"""

from __future__ import annotations


class EInvoicingError(Exception):
    """Root exception for all e-invoicing errors raised by this package."""


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class ValidationError(EInvoicingError):
    """A document, field, or identifier failed validation."""


class PartyValidationError(ValidationError):
    """Seller or buyer party block is invalid.

    Args:
        errors: List of validation error messages.
        party_role: 'seller' or 'buyer' for diagnostics.
    """

    def __init__(self, errors: list[str], party_role: str = "party") -> None:
        self.errors = errors
        self.party_role = party_role
        super().__init__(f"{party_role} validation failed: {'; '.join(errors)}")


class XSDValidationError(ValidationError):
    """XML document failed XSD schema validation.

    Args:
        errors: List of lxml error strings from XMLSchema.error_log.
        schema_version: The schema version that was applied.
    """

    def __init__(self, errors: list[str], schema_version: str = "unknown") -> None:
        self.errors = errors
        self.schema_version = schema_version
        summary = errors[0] if len(errors) == 1 else f"{len(errors)} errors"
        super().__init__(f"XSD validation ({schema_version}) failed: {summary}")


# ---------------------------------------------------------------------------
# Generation errors
# ---------------------------------------------------------------------------


class DocumentGenerationError(EInvoicingError):
    """Failed to generate a document (XML assembly, template, etc.)."""


# ---------------------------------------------------------------------------
# Transport / auth errors
# ---------------------------------------------------------------------------


class AuthenticationError(EInvoicingError):
    """OAuth2 token retrieval or renewal failed."""


class PlatformError(EInvoicingError):
    """An external national platform returned an error response.

    Args:
        status_code: HTTP status code from the platform.
        message: Human-readable error from the platform's error body.
        error_code: Platform-specific error code (optional).
    """

    def __init__(self, status_code: int, message: str, error_code: str | None = None) -> None:
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(f"Platform error {status_code}: {message}")
