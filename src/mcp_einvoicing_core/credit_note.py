"""EN 16931 credit note model.

Extends ``EN16931Invoice`` with credit-note-specific fields required by
EN 16931-1:2017 for document type codes 381 (commercial credit note),
383 (debit note), 384 (corrected invoice), and 385 (consolidated credit note).

The ``BillingReference`` captures the original invoice this credit note
refers to (BT-25 / BT-26), which is mandatory for credit notes per EN 16931
business rule BR-55.

Amounts on ``EN16931CreditNote`` are positive. The credit polarity is carried
by the ``document_type_code`` field, not by negated amounts (EN 16931 rule
BR-CO-25).
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from mcp_einvoicing_core.en16931 import EN16931Invoice


class BillingReference(BaseModel):
    """Reference to the original invoice a credit note corrects.

    Maps to:
      UBL:  cac:BillingReference / cac:InvoiceDocumentReference
      CII:  ram:InvoiceReferencedDocument (within ApplicableHeaderTradeAgreement)
    """

    invoice_number: str = Field(
        ..., description="Original invoice number (BT-25)"
    )
    issue_date: Optional[date] = Field(
        None, description="Original invoice issue date (BT-26)"
    )


class EN16931CreditNote(EN16931Invoice):
    """EN 16931 credit note, extending the base invoice model.

    Sets ``invoice_type_code`` to a credit-note family code and requires a
    ``billing_reference`` pointing to the original invoice.
    """

    invoice_type_code: Literal["381", "383", "384", "385"] = Field(
        "381",
        description=(
            "UNCL1001 document type code: "
            "381=commercial credit note, 383=debit note, "
            "384=corrected invoice, 385=consolidated credit note"
        ),
    )
    billing_reference: BillingReference = Field(
        ...,
        description="Reference to the original invoice this credit note corrects (BT-25/BT-26)",
    )

    @model_validator(mode="after")
    def _sync_preceding_invoice_fields(self) -> "EN16931CreditNote":
        """Keep the base class preceding_invoice_* fields in sync with billing_reference."""
        if self.preceding_invoice_reference is None:
            object.__setattr__(
                self,
                "preceding_invoice_reference",
                self.billing_reference.invoice_number,
            )
        if self.preceding_invoice_date is None and self.billing_reference.issue_date is not None:
            object.__setattr__(
                self,
                "preceding_invoice_date",
                self.billing_reference.issue_date,
            )
        return self
