"""
Shared Pydantic v2 models for mcp-einvoicing-core.

These models represent the **country-agnostic** invoice data concepts.
Every country adapter maps its own format (FatturaPA, UBL, Factur-X, ZUGFeRD…)
to and from these models.

Mapping notes:
  IT (FatturaPA):
    TaxIdentifier   → IdFiscaleIVA / CodiceFiscale
    PartyAddress    → Sede (Indirizzo, CAP, Comune, Nazione)
    InvoiceParty    → CedentePrestatore / CessionarioCommittente
    InvoiceLineItem → DettaglioLinee
    VATSummary      → DatiRiepilogo
    PaymentTerms    → DatiPagamento / DettaglioPagamento
    InvoiceDocument → FatturaElettronica (assembled by generate_fattura_xml)

  FR (XP Z12-013):
    InvoiceParty    → company/establishment in Directory Service
    InvoiceDocument → the binary flow submitted via submit_flow
    (FR doesn't decompose invoices into structured fields at MCP tool level — it
     operates on pre-built binary files. These models are used for directory tools.)

[DECISION: Optional country-specific fields use extra Pydantic Field metadata or
 are handled by subclassing in country packages, not by adding nullable fields
 to the base model for each country.]
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Primitive building blocks
# ---------------------------------------------------------------------------


class TaxIdentifier(BaseModel):
    """A tax / VAT identifier tied to a country.

    Captures the IdFiscaleIVA pattern (IT), NIP (PL), Steuernummer (DE), NIF (ES),
    BTW-nummer (BE) uniformly.

    country_code: ISO 3166-1 alpha-2 (e.g. 'IT', 'FR', 'DE').
    identifier:   The raw tax number string (no spaces, no prefix).
    """

    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    identifier: str = Field(..., min_length=1, max_length=50)

    @field_validator("country_code")
    @classmethod
    def upper_country(cls, v: str) -> str:
        return v.upper()


class PartyAddress(BaseModel):
    """Postal address of a party's registered office.

    Maps to:
      IT → Sede (Indirizzo / CAP / Comune / Nazione)
      UBL → PostalAddress
      ZUGFeRD → ram:PostalTradeAddress
    """

    street: str = Field(..., description="Street address (via, rue, Straße…)")
    postal_code: str = Field(..., description="Postal / ZIP code")
    city: str = Field(..., description="City / municipality")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    province: Optional[str] = Field(
        default=None,
        description="Province / region code. Required by IT (Provincia) and ES (Provincia).",
    )

    @field_validator("country_code")
    @classmethod
    def upper_country(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Party
# ---------------------------------------------------------------------------


class InvoiceParty(BaseModel):
    """Seller (CedentePrestatore / Supplier) or buyer (CessionarioCommittente / Customer).

    Supports both legal entities (name) and natural persons (first_name + last_name).
    At least one of {name} or {first_name + last_name} must be provided.

    tax_id:         Primary VAT/fiscal identifier (required).
    alt_tax_id:     Secondary identifier (e.g. IT CodiceFiscale alongside IdFiscaleIVA).
    address:        Registered office address.
    """

    tax_id: TaxIdentifier
    alt_tax_id: Optional[str] = Field(
        default=None,
        description=(
            "Alternative national identifier. "
            "IT: CodiceFiscale (16-char individual / 11-digit company). "
            "ES: NIF when IdFiscale differs. Ignored for countries that don't use it."
        ),
    )
    name: Optional[str] = Field(default=None, description="Legal entity name (Denominazione)")
    first_name: Optional[str] = Field(default=None, description="First name (natural person)")
    last_name: Optional[str] = Field(default=None, description="Last name (natural person)")
    address: Optional[PartyAddress] = None

    @model_validator(mode="after")
    def check_identity(self) -> "InvoiceParty":
        has_entity = bool(self.name)
        has_person = bool(self.first_name and self.last_name)
        if not has_entity and not has_person:
            raise ValueError(
                "Either 'name' (legal entity) or both 'first_name'+'last_name' (natural person) "
                "must be provided."
            )
        if has_entity and (self.first_name or self.last_name):
            raise ValueError("'name' is mutually exclusive with 'first_name'/'last_name'.")
        return self

    @property
    def display_name(self) -> str:
        """Returns name for legal entities, 'FirstName LastName' for persons."""
        if self.name:
            return self.name
        return f"{self.first_name} {self.last_name}"


# ---------------------------------------------------------------------------
# Document body
# ---------------------------------------------------------------------------


class InvoiceLineItem(BaseModel):
    """A single invoice line (DettaglioLinee / cac:InvoiceLine / ram:IncludedSupplyChainTradeLineItem).

    vat_rate: VAT percentage (0.0–100.0). Use 0.0 with vat_exemption_code for exempt lines.
    vat_exemption_code: Country-specific exemption code (IT: N1–N7, DE: S/Z/E, BE: VATEX-EU-...).
    """

    line_number: int = Field(..., ge=1, le=9999)
    description: str = Field(..., max_length=1000)
    quantity: Optional[Decimal] = Field(default=None, description="Quantity. Omit for lump sums.")
    unit_of_measure: Optional[str] = Field(default=None, max_length=10)
    unit_price: Decimal = Field(..., description="Unit price before VAT")
    total_price: Decimal = Field(..., description="Total line amount before VAT")
    vat_rate: Decimal = Field(default=Decimal("22"), ge=Decimal("0"), le=Decimal("100"))
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    vat_exemption_code: Optional[str] = Field(
        default=None,
        description="Country-specific VAT exemption code. Required when vat_rate is 0.",
    )

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


class VATSummary(BaseModel):
    """VAT summary entry for a group of lines sharing the same rate.

    Maps to IT DatiRiepilogo, UBL TaxTotal/TaxSubtotal, ZUGFeRD ram:ApplicableTradeTax.
    """

    vat_rate: Decimal = Field(..., ge=Decimal("0"), le=Decimal("100"))
    taxable_base: Decimal = Field(..., description="Net amount subject to this VAT rate")
    vat_amount: Decimal = Field(..., description="VAT amount (taxable_base × vat_rate / 100)")
    vat_exemption_code: Optional[str] = Field(
        default=None,
        description="Exemption code when vat_rate is 0",
    )


class PaymentTerms(BaseModel):
    """Payment terms and method.

    Maps to IT DatiPagamento, UBL PaymentMeans, ZUGFeRD ram:SpecifiedTradePaymentTerms.

    [AMBIGUITY: IT uses structured codes (TP01/02/03 + MP01-23). UBL and ZUGFeRD use
     free-text terms + UNCL4461 payment means codes. The base model uses free-form
     strings to remain format-neutral; country validators enforce their own code sets.]
    Option A: Store raw country codes → simpler, no translation layer needed.
    Option B: Use enums mapped per country → more type-safe but requires maintenance.
    Chosen: Option A (raw strings). Rationale: code sets vary significantly (IT has 23
    payment methods, UBL UNCL4461 has 70+).
    """

    payment_terms_code: Optional[str] = Field(
        default=None,
        description="Country-specific payment terms code (IT: TP01/02/03, ES: contado/plazo)",
    )
    payment_method_code: str = Field(
        ...,
        description="Country-specific payment method code (IT: MP01-23, UBL: UNCL4461)",
    )
    amount: Decimal = Field(..., description="Payment amount")
    due_date: Optional[str] = Field(
        default=None,
        description="Payment due date (YYYY-MM-DD)",
    )
    iban: Optional[str] = Field(
        default=None,
        description="IBAN for bank transfers (validated by xml_utils.validate_iban)",
    )
    bank_name: Optional[str] = Field(
        default=None,
        description="Financial institution name",
    )
    bic: Optional[str] = Field(
        default=None,
        description="BIC/SWIFT code for international transfers",
    )


# ---------------------------------------------------------------------------
# Top-level document
# ---------------------------------------------------------------------------


class InvoiceDocument(BaseModel):
    """Country-agnostic invoice document envelope.

    Country adapters read/write this model via BaseDocumentGenerator.generate()
    and BaseDocumentParser.to_invoice_document().

    document_type: Country-specific code (IT: TD01–TD28, UBL: 380/381/384, DE: RE/GU…).
    transmission_format: Platform routing hint (IT: FPA12/FPR12, FR: B2B/B2BInt/B2C).
    """

    document_type: str = Field(..., description="Country-specific document type code")
    date: str = Field(..., description="Invoice date (YYYY-MM-DD)")
    number: str = Field(..., max_length=50, description="Invoice / document number")
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    transmission_format: Optional[str] = Field(
        default=None,
        description="Platform routing / format hint (FPA12, FPR12, B2B, etc.)",
    )
    seller: InvoiceParty
    buyer: InvoiceParty
    lines: list[InvoiceLineItem] = Field(default_factory=list)
    vat_summary: list[VATSummary] = Field(default_factory=list)
    payment: Optional[PaymentTerms] = None
    note: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Free-text description/reason (IT: Causale, UBL: Note)",
    )

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


class DocumentValidationResult(BaseModel):
    """Output of BaseDocumentValidator.validate().

    valid:    True if the document passed all checks.
    errors:   List of error strings (XSD errors, business rule violations…).
    warnings: Non-blocking issues (deprecated codes, optional field usage…).
    metadata: Format-specific metadata extracted during validation
              (e.g. versione, namespace, schema_version).
    """

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a plain dict suitable for MCP tool responses."""
        result: dict = {"valid": self.valid, "errors": self.errors}
        if self.warnings:
            result["warnings"] = self.warnings
        if self.metadata:
            result.update(self.metadata)
        return result
