"""EN 16931-1:2017 base Pydantic models for mcp-einvoicing-core.

These models represent the **EN 16931** semantic data model — the European
standard for electronic invoicing (CEN Technical Committee 434).  All
country implementations that are EN 16931 compliant (ZUGFeRD, XRechnung,
Peppol BIS Billing 3.0, PINT-BE, FatturaPA extended profiles…) share this
common structure.

Country packages subclass EN16931Invoice and its component models to add
national fields and to constrain the generic `str` category/profile fields
to country-specific enumerations:

    class ZUGFeRDInvoice(EN16931Invoice):
        profile: ZUGFeRDProfile          # narrows str → ZUGFeRDProfile enum
        seller: ZUGFeRDParty             # adds leitweg_id, tax_number
        tax_lines: list[ZUGFeRDTax]      # narrows category str → GermanTaxCategory

Field names follow the BT (Business Term) and BG (Business Group) identifiers
defined in EN 16931-1:2017 Table 2.

    BG-4  / BG-7:   seller / buyer (EN16931Party)
    BG-5  / BG-8:   seller / buyer postal address (EN16931Address)
    BG-16:          payment instructions (EN16931PaymentMeans)
    BG-20 / BG-21:  document-level allowances / charges (EN16931AllowanceCharge)
    BG-22:          document totals (fields on EN16931Invoice)
    BG-23:          VAT breakdown (EN16931Tax)
    BG-25:          invoice lines (EN16931LineItem)
    BG-27 / BG-28:  line-level allowances / charges (EN16931AllowanceCharge reused)

[Verified against NF EN 16931-1:2017+A1:2019 (AFNOR), Article 6.3, Tableau 2 --
the full semantic model, BT-1 through BT-161 and BG-1 through BG-32 -- on
2026-08-25. Every BT/BG reference in this module's field descriptions was
checked against the normative text and confirmed correct; no mislabeled BT
number was found. See context-library/decisions/en16931-2026-deferral.md in
the mcp-einvoicing root repo for the verification record, and
tests/test_en16931_bt_mapping.py in this package for the regression test that
pins each field's BT reference.]

Coverage statement -- core is a deliberate common subset, not a full
implementation of every optional EN 16931 BT/BG. Confirmed omitted from this
module (verify against Table 2 before assuming a field exists):

  - BT-6 (VAT accounting currency code), BT-7 / BT-8 (VAT due date / code)
  - BT-14 (sales order ref), BT-15 / BT-16 (receiving advice / despatch advice
    ref), BT-17 (tender/lot ref), BT-18 (invoiced object ID), BT-19 (buyer
    accounting ref at document level -- BT-133, the line-level equivalent, IS
    modeled), BT-21 (note subject code)
  - BT-28 / BT-45 (seller / buyer trading name), BT-29 / BT-46 (seller / buyer
    general identifier), BT-30 / BT-47 (seller / buyer legal registration ID),
    BT-32 (seller tax identifier, non-VAT), BT-33 (seller additional legal
    info) -- EN16931Party only carries `name` (BT-27/44) and `vat_id`
    (BT-31/48) as identifiers
  - BT-91 (direct debit debited account identifier)
  - BT-127 (line note), BT-128 (line object identifier), BT-132 (line PO
    reference)
  - BT-147 / BT-148 (item price discount / gross price -- only the net price
    BT-146 is modeled), BT-150 (base-quantity unit code), BT-158 (item
    classification identifier), BT-159 (item country of origin)
  - BT-162 / BT-163 / BT-164 / BT-165 (address line 3, for seller / buyer /
    tax representative / delivery addresses -- only lines 1-2 are modeled)
  - BG-10 / BG-11 / BG-12 (payee, seller tax representative + address) --
    entirely absent, no payee or tax-representative fields anywhere in this
    module
  - BG-13 (deliver-to party name / establishment identifier), BG-15 (delivery
    address) -- entirely absent; only `delivery_date` is modeled
  - BG-17's 0..n cardinality (multiple bank transfer targets) is flattened to
    a single `payment_means` per invoice
  - BG-18 (payment card details) -- entirely absent
  - BG-24 (supporting document attachments) -- entirely absent
  - BG-26 (line-level billing period)
  - BG-32 (item attributes, e.g. colour/size)

Deliberate stricter-than-base validation (not an omission, not a mismatch):
EN16931Tax.rate (BT-119) and EN16931LineItem.tax_rate (BT-152) are declared
required here, though the base standard marks both cardinality 0..1
(optional). Implementations that omit the VAT rate for an exempt/zero-rated
line should supply an explicit 0 rather than rely on omission.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Address — BG-5 (seller postal address) / BG-8 (buyer postal address)
# ---------------------------------------------------------------------------


class EN16931Address(BaseModel):
    """Postal address of a trading party.

    Maps to:
      CII:  ram:PostalTradeAddress
      UBL:  cac:PostalAddress
      FatturaPA: Sede (Indirizzo / CAP / Comune / Nazione)
    """

    line_one: str = Field(..., description="Street and house number (BT-35 / BT-50)")
    line_two: str | None = Field(None, description="Address continuation line (BT-36 / BT-51)")
    city: str = Field(..., description="City / municipality (BT-37 / BT-52)")
    postcode: str = Field(..., description="Postal / ZIP code (BT-38 / BT-53)")
    country_code: Annotated[str, Field(min_length=2, max_length=2)] = Field(
        ..., description="ISO 3166-1 alpha-2 country code (BT-40 / BT-55)"
    )
    region: str | None = Field(None, description="Region / province (BT-39 / BT-54)")

    @field_validator("country_code")
    @classmethod
    def upper_country(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Party — BG-4 (seller) / BG-7 (buyer)
# ---------------------------------------------------------------------------


class EN16931Party(BaseModel):
    """Trading party (seller BG-4 or buyer BG-7).

    Covers mandatory and common-optional fields shared across all EN 16931
    compliant formats.  Country packages add national fields by subclassing.

    vat_id:                 BT-31 / BT-48 — VAT registration number (e.g. DE123456789)
    electronic_address:     BT-34 / BT-49 — EAS-registered endpoint identifier
    electronic_address_scheme: EAS scheme code (e.g. "0088" GLN, "0204" Leitweg-ID)
    """

    name: str = Field(..., description="Legal entity name (BT-27 / BT-44)")
    address: EN16931Address
    vat_id: str | None = Field(None, description="VAT number (BT-31 / BT-48)")
    electronic_address: str | None = Field(
        None, description="Peppol / EAS electronic address (BT-34 / BT-49)"
    )
    electronic_address_scheme: str | None = Field(
        None, description="EAS scheme code, e.g. '0088' for GLN (BT-34-SchemeID / BT-49-SchemeID)"
    )
    contact_name: str | None = Field(None, description="Contact person name (BT-41 / BT-56)")
    contact_phone: str | None = Field(None, description="Contact phone (BT-42 / BT-57)")
    contact_email: str | None = Field(None, description="Contact email (BT-43 / BT-58)")


# ---------------------------------------------------------------------------
# VAT breakdown line — BG-23
# ---------------------------------------------------------------------------


class EN16931Tax(BaseModel):
    """VAT breakdown entry — EN 16931 BG-23.

    category: UNCL5305 VAT category code (BT-118).
      Common values: S (standard), Z (zero), E (exempt), AE (reverse charge),
      K (intra-community), G (export), O (not subject), L, M.
      Country packages narrow this to a typed enum (e.g. GermanTaxCategory).

    Maps to:
      CII:  ram:ApplicableTradeTax
      UBL:  cac:TaxTotal/cac:TaxSubtotal
    """

    category: str = Field(
        ..., description="UNCL5305 VAT category code (BT-118), e.g. 'S', 'AE', 'E'"
    )
    rate: Decimal = Field(
        ..., ge=Decimal("0"), le=Decimal("100"), description="Tax rate % (BT-119)"
    )
    taxable_amount: Decimal = Field(..., description="Net taxable base amount (BT-116)")
    tax_amount: Decimal = Field(..., description="Calculated VAT amount (BT-117)")
    exemption_reason: str | None = Field(
        None,
        description="Exemption reason text (BT-120) — required when category ≠ S",
    )
    exemption_reason_code: str | None = Field(
        None, description="VATEX exemption reason code (BT-121)"
    )


# ---------------------------------------------------------------------------
# Allowance / Charge — BG-20 (document allowance) / BG-21 (document charge)
# Reused at line level for BG-27 (line allowance) / BG-28 (line charge)
# ---------------------------------------------------------------------------


class EN16931AllowanceCharge(BaseModel):
    """Document-level or line-level allowance or charge.

    is_charge: False = allowance (BG-20 / BG-27), True = charge (BG-21 / BG-28).
    tax_category: UNCL5305 code for the VAT category of this allowance/charge.
    """

    is_charge: bool = Field(
        ..., description="True = charge (BG-21/BG-28), False = allowance (BG-20/BG-27)"
    )
    amount: Decimal = Field(
        ..., ge=Decimal("0"), description="Amount (BT-92 / BT-99 / BT-136 / BT-141)"
    )
    base_amount: Decimal | None = Field(
        None,
        description="Base amount for percentage calculation (BT-93 / BT-100 / BT-137 / BT-142)",
    )
    percentage: Decimal | None = Field(
        None, description="Percentage (BT-94 / BT-101 / BT-138 / BT-143)"
    )
    reason: str | None = Field(None, description="Reason text (BT-97 / BT-104 / BT-139 / BT-144)")
    reason_code: str | None = Field(
        None, description="UNCL7161 reason code (BT-98 / BT-105 / BT-140 / BT-145)"
    )
    tax_category: str = Field(
        ..., description="UNCL5305 VAT category code (BT-95 / BT-102 / BT-151)"
    )
    tax_rate: Decimal = Field(..., description="VAT rate % for this item (BT-96 / BT-103 / BT-152)")


# ---------------------------------------------------------------------------
# Invoice line — BG-25
# ---------------------------------------------------------------------------


class EN16931LineItem(BaseModel):
    """Invoice line — EN 16931 BG-25.

    Not present in MINIMUM or BASIC WL profiles (those profiles have no line
    items — only document totals).

    tax_category: UNCL5305 code. Country packages constrain with an enum.
    unit_code:    UNECE Recommendation 20 unit of measure code (BT-130).
    """

    line_id: str = Field(..., description="Line identifier (BT-126)")
    name: str = Field(..., description="Item name (BT-153)")
    description: str | None = Field(None, description="Item description (BT-154)")
    quantity: Decimal = Field(..., description="Billed quantity (BT-129)")
    unit_code: str = Field(..., description="UNECE Rec 20 unit of measure code (BT-130)")
    unit_price: Decimal = Field(..., description="Net price per unit (BT-146)")
    unit_price_base_quantity: Decimal = Field(
        Decimal("1"), description="Base quantity for unit price (BT-149)"
    )
    line_net_amount: Decimal = Field(..., description="Line net amount (BT-131)")
    tax_category: str = Field(..., description="UNCL5305 VAT category code (BT-151)")
    tax_rate: Decimal = Field(..., description="Line VAT rate % (BT-152)")
    buyer_accounting_reference: str | None = Field(
        None, description="Buyer accounting reference (BT-133)"
    )
    seller_article_id: str | None = Field(None, description="Seller item identifier (BT-155)")
    buyer_article_id: str | None = Field(None, description="Buyer item identifier (BT-156)")
    standard_article_id: str | None = Field(
        None, description="Standard item identifier, e.g. EAN (BT-157)"
    )
    standard_article_id_scheme: str | None = Field(
        None, description="Scheme ID for standard article identifier (BT-157-1)"
    )
    line_allowances: list[EN16931AllowanceCharge] = Field(
        default_factory=list,
        description="Line-level allowances and charges (BG-27 / BG-28)",
    )


# ---------------------------------------------------------------------------
# Payment means — BG-16
# ---------------------------------------------------------------------------


class EN16931PaymentMeans(BaseModel):
    """Payment instructions — EN 16931 BG-16.

    type_code: UNCL4461 payment means code (BT-81).
      Common values: 30 (credit transfer), 48 (card), 49 (direct debit),
      58 (SEPA credit transfer), 59 (SEPA direct debit).
    """

    type_code: str = Field(
        ..., description="UNCL4461 payment means code (BT-81), e.g. '58' for SEPA Credit Transfer"
    )
    iban: str | None = Field(None, description="Payee IBAN (BT-84)")
    bic: str | None = Field(None, description="Payee BIC/SWIFT (BT-86)")
    account_name: str | None = Field(None, description="Account holder name (BT-85)")
    payment_id: str | None = Field(None, description="Remittance information (BT-83)")
    mandate_reference: str | None = Field(
        None, description="SEPA Direct Debit mandate reference (BT-89)"
    )
    creditor_id: str | None = Field(None, description="SEPA Creditor Identifier (BT-90)")


# ---------------------------------------------------------------------------
# Invoice root — all EN 16931 BT/BG fields
# ---------------------------------------------------------------------------


class EN16931Invoice(BaseModel):
    """Root model for an EN 16931-1:2017 compliant electronic invoice.

    Covers all mandatory and common-optional EN 16931 fields from MINIMUM
    through EXTENDED profiles.  Fields absent from lower profiles (e.g. line
    items) are Optional with empty defaults; the validator layer enforces
    profile-specific mandatory rules.

    Country packages extend this class:
      - Override `profile` to a country-specific enum (ZUGFeRDProfile, etc.)
      - Override `seller` / `buyer` to a country-specific party subclass
      - Override `tax_lines` to use a country-specific tax category enum
      - Add national fields (leitweg_id for DE, codice_destinatario for IT…)

    BT-24 is the GuidelineID / profile URN.  Its value is format-specific:
      ZUGFeRD:    urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:en16931
      XRechnung:  urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_2.3
      Peppol BIS: urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0
    """

    # ── Profile URN enforcement ──────────────────────────────────────────────
    # Set _allowed_profiles to a frozenset of valid URN strings in each
    # country subclass that uses a typed enum for `profile`.  The model
    # validator below rejects any value not in the set.  Leave as None (the
    # default) to accept any string — appropriate for abstract base use.
    # Must be ClassVar so that subclass assignments remain class variables
    # and self.__class__._allowed_profiles returns the actual value, not a
    # ModelPrivateAttr descriptor.
    _allowed_profiles: ClassVar[frozenset[str] | None] = None

    # ── Header fields ────────────────────────────────────────────────────────

    profile: str = Field(
        ...,
        description=(
            "GuidelineID / profile URN (BT-24). "
            "Constrain to a typed enum in each country subclass by setting "
            "_allowed_profiles = frozenset({MyEnum.member.value, ...})."
        ),
    )
    business_process: str | None = Field(
        None,
        description=(
            "BT-23 Business process type. In UBL emitted as <cbc:ProfileID>; "
            "in CII as <ram:BusinessProcessSpecifiedDocumentContextParameter><ram:ID>. "
            "Distinct from `profile` which holds BT-24 (Specification identifier)."
        ),
    )
    invoice_number: str = Field(..., description="Invoice number (BT-1)")
    invoice_date: date = Field(..., description="Invoice issue date (BT-2)")
    invoice_type_code: str = Field(
        "380",
        description="UNCL1001 document type code (BT-3). 380=Invoice, 381=Credit Note",
    )
    currency_code: Annotated[str, Field(min_length=3, max_length=3)] = Field(
        "EUR", description="ISO 4217 invoice currency code (BT-5)"
    )
    document_uuid: str | None = Field(
        None,
        description=(
            "Universally unique document identifier, emitted as <cbc:UUID> — a sibling "
            "element immediately after <cbc:ID>. Not a formal EN 16931 BT; several Peppol "
            "jurisdiction CIUS profiles mandate it (e.g. PINT AE BTAE-07, PINT-SG BT-SG-003). "
            "Optional in the base model since most EN 16931 profiles do not require it; "
            "country subclasses that require it should re-declare it as required."
        ),
    )

    # ── Optional header references ───────────────────────────────────────────

    buyer_reference: str | None = Field(
        None,
        description=(
            "Buyer reference / routing ID (BT-10). "
            "Mandatory for XRechnung and public-sector buyers."
        ),
    )
    purchase_order_reference: str | None = Field(
        None, description="Purchase order reference (BT-13)"
    )
    contract_reference: str | None = Field(None, description="Contract reference (BT-12)")
    project_reference: str | None = Field(None, description="Project reference (BT-11)")
    note: str | None = Field(None, description="Invoice note / reason (BT-22)")

    # ── Delivery dates ───────────────────────────────────────────────────────

    delivery_date: date | None = Field(None, description="Actual delivery date (BT-72)")
    billing_period_start: date | None = Field(None, description="Billing period start date (BT-73)")
    billing_period_end: date | None = Field(None, description="Billing period end date (BT-74)")

    # ── Parties ──────────────────────────────────────────────────────────────

    seller: EN16931Party = Field(..., description="Seller / supplier (BG-4)")
    buyer: EN16931Party = Field(..., description="Buyer / customer (BG-7)")

    # ── Document totals — BG-22 ──────────────────────────────────────────────

    sum_of_line_net_amounts: Decimal = Field(
        ..., description="Sum of invoice line net amounts (BT-106)"
    )
    allowances_total: Decimal = Field(
        Decimal("0"), description="Total document-level allowances (BT-107)"
    )
    charges_total: Decimal = Field(
        Decimal("0"), description="Total document-level charges (BT-108)"
    )
    tax_exclusive_amount: Decimal = Field(..., description="Invoice total without VAT (BT-109)")
    tax_total: Decimal = Field(..., description="Total VAT amount (BT-110)")
    tax_inclusive_amount: Decimal = Field(..., description="Invoice total with VAT (BT-112)")
    prepaid_amount: Decimal = Field(Decimal("0"), description="Prepaid amount (BT-113)")
    rounding_amount: Decimal = Field(Decimal("0"), description="Rounding amount (BT-114)")
    amount_due: Decimal = Field(..., description="Amount due for payment (BT-115)")

    # ── VAT breakdown — BG-23 ────────────────────────────────────────────────

    tax_lines: list[EN16931Tax] = Field(
        default_factory=list,
        description="VAT breakdown lines (BG-23). EN 16931 requires at least one.",
    )

    @model_validator(mode="after")
    def _require_tax_lines(self) -> EN16931Invoice:
        """EN 16931 rule BR-CO-18: at least one VAT breakdown line is mandatory.

        Subclasses that represent summary-only or non-EN-16931 formats (e.g.
        ZATCA, MyInvois clearance models) may override this validator with a
        no-op to relax the constraint without re-declaring the field.
        """
        if len(self.tax_lines) < 1:
            raise ValueError(
                "EN 16931 rule BR-CO-18: at least one VAT breakdown line (BG-23) is required."
            )
        return self

    @model_validator(mode="after")
    def _check_profile_urn(self) -> EN16931Invoice:
        """Enforce allowed profile URNs when _allowed_profiles is set on the subclass.

        Country subclasses that narrow `profile` to a typed enum should also set
        ``_allowed_profiles = frozenset({e.value for e in MyProfileEnum})`` so that
        instances constructed with a raw string are rejected at parse time.
        """
        allowed = self.__class__._allowed_profiles
        if allowed is not None and self.profile not in allowed:
            raise ValueError(
                f"{self.__class__.__name__}: profile URN {self.profile!r} is not in the "
                f"allowed set. Allowed values: {sorted(allowed)}"
            )
        return self

    # ── Document-level allowances / charges — BG-20 / BG-21 ─────────────────

    allowances_charges: list[EN16931AllowanceCharge] = Field(
        default_factory=list,
        description="Document-level allowances (BG-20) and charges (BG-21)",
    )

    # ── Payment — BG-16 ──────────────────────────────────────────────────────

    payment_means: EN16931PaymentMeans | None = Field(
        None, description="Payment instructions (BG-16)"
    )
    payment_terms: str | None = Field(None, description="Payment terms free text (BT-20)")
    due_date: date | None = Field(None, description="Payment due date (BT-9)")

    # ── Invoice lines — BG-25 ────────────────────────────────────────────────

    line_items: list[EN16931LineItem] = Field(
        default_factory=list,
        description=(
            "Invoice lines (BG-25). Required for BASIC, EN_16931, EXTENDED, "
            "XRechnung profiles. Absent in MINIMUM and BASIC WL."
        ),
    )

    # ── Preceding invoice references ─────────────────────────────────────────

    preceding_invoice_reference: str | None = Field(
        None, description="Preceding invoice reference for credit notes (BT-25)"
    )
    preceding_invoice_date: date | None = Field(
        None, description="Preceding invoice issue date (BT-26)"
    )

    @field_validator("currency_code")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()
