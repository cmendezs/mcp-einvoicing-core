"""Regression test for the field -> Business Term (BT) mappings in en16931.py.

Verified 2026-08-25 against NF EN 16931-1:2017+A1:2019 (AFNOR), Article 6.3,
Tableau 2 -- BT-1 through BT-161, BG-1 through BG-32. See
mcp-einvoicing-core/src/mcp_einvoicing_core/en16931.py module docstring and
context-library/decisions/en16931-2026-deferral.md in the root repo for the
verification record. This test pins each field's declared BT reference so an
accidental edit to a Field(description=...) string cannot silently drift the
field -> BT mapping without a test failure.
"""

from __future__ import annotations

from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931AllowanceCharge,
    EN16931Invoice,
    EN16931LineItem,
    EN16931Party,
    EN16931PaymentMeans,
    EN16931Tax,
)

# field_name -> BT reference(s) expected to appear in the Field(description=...) string.
_ADDRESS_BT = {
    "line_one": "BT-35 / BT-50",
    "line_two": "BT-36 / BT-51",
    "city": "BT-37 / BT-52",
    "postcode": "BT-38 / BT-53",
    "country_code": "BT-40 / BT-55",
    "region": "BT-39 / BT-54",
}

_PARTY_BT = {
    "name": "BT-27 / BT-44",
    "vat_id": "BT-31 / BT-48",
    "electronic_address": "BT-34 / BT-49",
    "electronic_address_scheme": "BT-34-SchemeID / BT-49-SchemeID",
    "contact_name": "BT-41 / BT-56",
    "contact_phone": "BT-42 / BT-57",
    "contact_email": "BT-43 / BT-58",
}

_TAX_BT = {
    "category": "BT-118",
    "rate": "BT-119",
    "taxable_amount": "BT-116",
    "tax_amount": "BT-117",
    "exemption_reason": "BT-120",
    "exemption_reason_code": "BT-121",
}

_ALLOWANCE_CHARGE_BT = {
    "amount": "BT-92 / BT-99 / BT-136 / BT-141",
    "base_amount": "BT-93 / BT-100 / BT-137 / BT-142",
    "percentage": "BT-94 / BT-101 / BT-138 / BT-143",
    "reason": "BT-97 / BT-104 / BT-139 / BT-144",
    "reason_code": "BT-98 / BT-105 / BT-140 / BT-145",
    "tax_category": "BT-95 / BT-102 / BT-151",
    "tax_rate": "BT-96 / BT-103 / BT-152",
}

_LINE_ITEM_BT = {
    "line_id": "BT-126",
    "name": "BT-153",
    "description": "BT-154",
    "quantity": "BT-129",
    "unit_code": "BT-130",
    "unit_price": "BT-146",
    "unit_price_base_quantity": "BT-149",
    "line_net_amount": "BT-131",
    "tax_category": "BT-151",
    "tax_rate": "BT-152",
    "buyer_accounting_reference": "BT-133",
    "seller_article_id": "BT-155",
    "buyer_article_id": "BT-156",
    "standard_article_id": "BT-157",
    "standard_article_id_scheme": "BT-157-1",
}

_PAYMENT_MEANS_BT = {
    "type_code": "BT-81",
    "iban": "BT-84",
    "bic": "BT-86",
    "account_name": "BT-85",
    "payment_id": "BT-83",
    "mandate_reference": "BT-89",
    "creditor_id": "BT-90",
}

_INVOICE_BT = {
    "profile": "BT-24",
    "business_process": "BT-23",
    "invoice_number": "BT-1",
    "invoice_date": "BT-2",
    "invoice_type_code": "BT-3",
    "currency_code": "BT-5",
    "buyer_reference": "BT-10",
    "purchase_order_reference": "BT-13",
    "contract_reference": "BT-12",
    "project_reference": "BT-11",
    "note": "BT-22",
    "delivery_date": "BT-72",
    "billing_period_start": "BT-73",
    "billing_period_end": "BT-74",
    "sum_of_line_net_amounts": "BT-106",
    "allowances_total": "BT-107",
    "charges_total": "BT-108",
    "tax_exclusive_amount": "BT-109",
    "tax_total": "BT-110",
    "tax_inclusive_amount": "BT-112",
    "prepaid_amount": "BT-113",
    "rounding_amount": "BT-114",
    "amount_due": "BT-115",
    "payment_terms": "BT-20",
    "due_date": "BT-9",
    "preceding_invoice_reference": "BT-25",
    "preceding_invoice_date": "BT-26",
}


def _assert_bt_mapping(model_cls: type, expected: dict[str, str]) -> None:
    fields = model_cls.model_fields
    for field_name, bt_ref in expected.items():
        assert field_name in fields, f"{model_cls.__name__}.{field_name} no longer exists"
        description = fields[field_name].description or ""
        assert bt_ref in description, (
            f"{model_cls.__name__}.{field_name} description {description!r} "
            f"no longer contains expected BT reference {bt_ref!r}"
        )


def test_en16931_address_bt_mapping() -> None:
    _assert_bt_mapping(EN16931Address, _ADDRESS_BT)


def test_en16931_party_bt_mapping() -> None:
    _assert_bt_mapping(EN16931Party, _PARTY_BT)


def test_en16931_tax_bt_mapping() -> None:
    _assert_bt_mapping(EN16931Tax, _TAX_BT)


def test_en16931_allowance_charge_bt_mapping() -> None:
    _assert_bt_mapping(EN16931AllowanceCharge, _ALLOWANCE_CHARGE_BT)


def test_en16931_line_item_bt_mapping() -> None:
    _assert_bt_mapping(EN16931LineItem, _LINE_ITEM_BT)


def test_en16931_payment_means_bt_mapping() -> None:
    _assert_bt_mapping(EN16931PaymentMeans, _PAYMENT_MEANS_BT)


def test_en16931_invoice_bt_mapping() -> None:
    _assert_bt_mapping(EN16931Invoice, _INVOICE_BT)


def test_en16931_tax_rate_and_line_tax_rate_stricter_than_base_standard() -> None:
    """BT-119 and BT-152 are cardinality 0..1 (optional) in the base standard,
    but core declares EN16931Tax.rate and EN16931LineItem.tax_rate as required.
    This is a deliberate, stricter-than-base validation choice (documented in
    the en16931.py module docstring coverage statement), not a BT mismatch --
    this test pins the intentional divergence so it is not "fixed" by accident.
    """
    assert EN16931Tax.model_fields["rate"].is_required()
    assert EN16931LineItem.model_fields["tax_rate"].is_required()
