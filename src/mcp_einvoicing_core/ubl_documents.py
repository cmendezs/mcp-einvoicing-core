"""Base model for non-invoice UBL/Peppol business document families.

Peppol/UBL defines many business document types beyond Invoice and CreditNote —
Order, OrderResponse (simple and advanced), OrderChange, OrderCancellation,
OrderAgreement, Invoice Response, and jurisdiction-specific extensions (e.g.
Singapore IMDA's Order Balance). These share a common UBL document envelope
but are otherwise unrelated to invoicing.

Per CLAUDE.md's canonical invoice tree rule, they are explicitly **outside**
that tree: never subclass ``InvoiceDocument`` or ``EN16931Invoice`` for a
non-invoice UBL document, and never subclass ``BaseUBLDocument`` for an
invoice or credit note.

Why a shared base here but not for MLS/EUSR/TSR: those are single, standalone
document types (``peppol.mls.MessageLevelStatus``,
``peppol.reporting.EndUserStatisticsReport``/``TransactionStatisticsReport``)
with no sibling documents sharing their envelope, so each is a plain
``BaseModel`` with its own build/parse/validate functions. The Peppol
Ordering family is a *family* of nine related document types sharing an
identical header shape — the same situation EN16931Invoice/InvoiceDocument
solve for the invoice family — so a shared base avoids nine-way duplication
of the same four header fields.

Country packages define per-document-type subclasses of ``BaseUBLDocument``
with the fields specific to that document type (order lines, response codes,
etc.), the same way DE/BE/FR subclass ``EN16931Invoice`` for their own
formats. ``sender``/``receiver`` here are ``PeppolParticipantId`` (scheme +
value) since that is the one piece of party identity every UBL document type
carries identically; full party detail (name, address, tax scheme) varies by
document type and belongs in the subclass.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from mcp_einvoicing_core.peppol import PeppolParticipantId


class BaseUBLDocument(BaseModel):
    """Common envelope shared by every non-invoice UBL/Peppol business document.

    Maps to the UBL document root's shared header elements:
      document_id      -> cbc:ID
      issue_date        -> cbc:IssueDate
      customization_id  -> cbc:CustomizationID (jurisdiction/profile URN)
      profile_id        -> cbc:ProfileID (Peppol business process identifier)
      sender            -> the document-type-specific *SupplierParty/*Party endpoint
      receiver          -> the document-type-specific *CustomerParty/*Party endpoint
    """

    document_id: str = Field(..., description="cbc:ID — this document's own identifier")
    issue_date: date = Field(..., description="cbc:IssueDate")
    customization_id: str = Field(
        ...,
        description=(
            "cbc:CustomizationID — jurisdiction/profile URN, e.g. "
            "urn:fdc:peppol.eu:poacc:trns:order:3"
        ),
    )
    profile_id: str = Field(
        ...,
        description=(
            "cbc:ProfileID — Peppol business process identifier, e.g. "
            "urn:fdc:peppol.eu:poacc:bis:order_only:3"
        ),
    )
    sender: PeppolParticipantId = Field(
        ..., description="Sender's Peppol participant identifier"
    )
    receiver: PeppolParticipantId = Field(
        ..., description="Receiver's Peppol participant identifier"
    )
