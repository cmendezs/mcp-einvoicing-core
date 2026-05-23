"""Tests for EN16931 UBL 2.1 and CII wire-format serialisers and parsers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931AllowanceCharge,
    EN16931Invoice,
    EN16931LineItem,
    EN16931Party,
    EN16931PaymentMeans,
    EN16931Tax,
)
from mcp_einvoicing_core.wire_formats import (
    EN16931CIIParser,
    EN16931CIISerializer,
    EN16931UBLParser,
    EN16931UBLSerializer,
    CII_NSMAP,
    UBL_NSMAP,
)

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

_PROFILE = "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"


def _make_invoice(**kwargs) -> EN16931Invoice:
    defaults = dict(
        profile=_PROFILE,
        invoice_number="INV-2026-001",
        invoice_date=date(2026, 5, 23),
        invoice_type_code="380",
        currency_code="EUR",
        seller=EN16931Party(
            name="Acme SA",
            address=EN16931Address(
                line_one="1 Rue de la Paix",
                city="Paris",
                postcode="75001",
                country_code="FR",
            ),
            vat_id="FR12345678901",
            electronic_address="0208:0123456789",
            electronic_address_scheme="0208",
        ),
        buyer=EN16931Party(
            name="ACME Belgium NV",
            address=EN16931Address(
                line_one="Avenue Louise 10",
                city="Brussels",
                postcode="1050",
                country_code="BE",
            ),
            vat_id="BE0123456789",
        ),
        sum_of_line_net_amounts=Decimal("100.00"),
        allowances_total=Decimal("0"),
        charges_total=Decimal("0"),
        tax_exclusive_amount=Decimal("100.00"),
        tax_total=Decimal("21.00"),
        tax_inclusive_amount=Decimal("121.00"),
        prepaid_amount=Decimal("0"),
        rounding_amount=Decimal("0"),
        amount_due=Decimal("121.00"),
        tax_lines=[
            EN16931Tax(
                category="S",
                rate=Decimal("21"),
                taxable_amount=Decimal("100.00"),
                tax_amount=Decimal("21.00"),
            )
        ],
        line_items=[
            EN16931LineItem(
                line_id="1",
                name="Consulting services",
                quantity=Decimal("1"),
                unit_code="HUR",
                unit_price=Decimal("100.00"),
                line_net_amount=Decimal("100.00"),
                tax_category="S",
                tax_rate=Decimal("21"),
            )
        ],
    )
    defaults.update(kwargs)
    return EN16931Invoice(**defaults)


# ---------------------------------------------------------------------------
# UBL serialiser tests
# ---------------------------------------------------------------------------


class TestUBLSerializer:
    def test_produces_bytes(self):
        xml = EN16931UBLSerializer().serialize(_make_invoice())
        assert isinstance(xml, bytes)
        assert xml.startswith(b"<?xml")

    def test_root_element_invoice(self):
        xml = EN16931UBLSerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        assert etree.QName(root.tag).localname == "Invoice"

    def test_root_element_credit_note(self):
        inv = _make_invoice(invoice_type_code="381")
        xml = EN16931UBLSerializer().serialize(inv)
        root = etree.fromstring(xml)
        assert etree.QName(root.tag).localname == "CreditNote"

    def test_mandatory_fields_present(self):
        xml = EN16931UBLSerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        assert root.find("cbc:ID", ns).text == "INV-2026-001"
        assert root.find("cbc:IssueDate", ns).text == "2026-05-23"
        assert root.find("cbc:DocumentCurrencyCode", ns).text == "EUR"
        assert root.find("cbc:CustomizationID", ns).text == _PROFILE

    def test_seller_name_present(self):
        xml = EN16931UBLSerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        }
        name = root.find(".//cac:AccountingSupplierParty//cbc:RegistrationName", ns)
        assert name is not None
        assert name.text == "Acme SA"

    def test_tax_total_present(self):
        xml = EN16931UBLSerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        }
        tax_amount = root.find(".//cac:TaxTotal/cbc:TaxAmount", ns)
        assert tax_amount is not None
        assert Decimal(tax_amount.text) == Decimal("21.00")

    def test_line_item_present(self):
        xml = EN16931UBLSerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        }
        lines = root.findall("cac:InvoiceLine", ns)
        assert len(lines) == 1
        name = lines[0].find(".//cbc:Name", ns)
        assert name.text == "Consulting services"

    def test_optional_note(self):
        inv = _make_invoice(note="Test note")
        xml = EN16931UBLSerializer().serialize(inv)
        root = etree.fromstring(xml)
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        note_el = root.find("cbc:Note", ns)
        assert note_el is not None
        assert note_el.text == "Test note"

    def test_payment_means_with_iban(self):
        inv = _make_invoice(
            payment_means=EN16931PaymentMeans(
                type_code="58",
                iban="BE68539007547034",
                bic="BNAGBEBB",
            ),
            due_date=date(2026, 6, 23),
        )
        xml = EN16931UBLSerializer().serialize(inv)
        root = etree.fromstring(xml)
        ns = {
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        }
        pm = root.find("cac:PaymentMeans", ns)
        assert pm is not None
        iban_el = pm.find(".//cbc:ID", ns)
        assert iban_el is not None
        assert iban_el.text == "BE68539007547034"

    def test_document_level_allowance(self):
        inv = _make_invoice(
            allowances_charges=[
                EN16931AllowanceCharge(
                    is_charge=False,
                    amount=Decimal("10.00"),
                    reason="Early payment discount",
                    tax_category="S",
                    tax_rate=Decimal("21"),
                )
            ]
        )
        xml = EN16931UBLSerializer().serialize(inv)
        root = etree.fromstring(xml)
        ns = {
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        }
        acs = root.findall("cac:AllowanceCharge", ns)
        assert len(acs) == 1
        charge_indicator = acs[0].find("cbc:ChargeIndicator", ns)
        assert charge_indicator.text == "false"


# ---------------------------------------------------------------------------
# UBL round-trip tests
# ---------------------------------------------------------------------------


class TestUBLRoundTrip:
    def _round_trip(self, invoice: EN16931Invoice) -> EN16931Invoice:
        xml = EN16931UBLSerializer().serialize(invoice)
        return EN16931UBLParser().parse(xml)

    def test_basic_fields_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert restored.invoice_number == original.invoice_number
        assert restored.invoice_date == original.invoice_date
        assert restored.currency_code == original.currency_code
        assert restored.profile == original.profile

    def test_totals_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert restored.tax_total == original.tax_total
        assert restored.amount_due == original.amount_due
        assert restored.tax_inclusive_amount == original.tax_inclusive_amount

    def test_seller_buyer_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert restored.seller.name == original.seller.name
        assert restored.seller.vat_id == original.seller.vat_id
        assert restored.buyer.name == original.buyer.name
        assert restored.buyer.address.country_code == original.buyer.address.country_code

    def test_line_items_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert len(restored.line_items) == len(original.line_items)
        assert restored.line_items[0].name == original.line_items[0].name
        assert restored.line_items[0].unit_price == original.line_items[0].unit_price

    def test_tax_lines_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert len(restored.tax_lines) == 1
        assert restored.tax_lines[0].category == "S"
        assert restored.tax_lines[0].rate == Decimal("21")

    def test_optional_fields_round_trip(self):
        original = _make_invoice(
            note="Test memo",
            buyer_reference="BR-2026",
            purchase_order_reference="PO-123",
            contract_reference="CTR-456",
            payment_terms="Net 30 days",
            due_date=date(2026, 6, 22),
        )
        restored = self._round_trip(original)
        assert restored.note == "Test memo"
        assert restored.buyer_reference == "BR-2026"
        assert restored.purchase_order_reference == "PO-123"
        assert restored.contract_reference == "CTR-456"
        assert restored.payment_terms == "Net 30 days"
        assert restored.due_date == date(2026, 6, 22)

    def test_preceding_invoice_round_trip(self):
        original = _make_invoice(
            invoice_type_code="381",
            preceding_invoice_reference="INV-2026-000",
            preceding_invoice_date=date(2026, 4, 1),
        )
        restored = self._round_trip(original)
        assert restored.preceding_invoice_reference == "INV-2026-000"
        assert restored.preceding_invoice_date == date(2026, 4, 1)


# ---------------------------------------------------------------------------
# CII serialiser tests
# ---------------------------------------------------------------------------


class TestCIISerializer:
    def test_produces_bytes(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        assert isinstance(xml, bytes)
        assert xml.startswith(b"<?xml")

    def test_root_element(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        assert etree.QName(root.tag).localname == "CrossIndustryInvoice"

    def test_profile_urn_present(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {"rsm": _RSM, "ram": _RAM}
        id_el = root.find(
            "rsm:ExchangedDocumentContext"
            "/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID",
            ns,
        )
        assert id_el is not None
        assert id_el.text == _PROFILE

    def test_invoice_number_present(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {"rsm": _RSM, "ram": _RAM}
        id_el = root.find("rsm:ExchangedDocument/ram:ID", ns)
        assert id_el is not None
        assert id_el.text == "INV-2026-001"

    def test_issue_date_format_102(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {"rsm": _RSM, "ram": _RAM, "udt": _UDT}
        dt_el = root.find(
            "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString", ns
        )
        assert dt_el is not None
        assert dt_el.text == "20260523"
        assert dt_el.get("format") == "102"

    def test_seller_name_in_cii(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {"rsm": _RSM, "ram": _RAM}
        name = root.find(
            "rsm:SupplyChainTradeTransaction"
            "/ram:ApplicableHeaderTradeAgreement"
            "/ram:SellerTradeParty/ram:Name",
            ns,
        )
        assert name is not None
        assert name.text == "Acme SA"

    def test_monetary_summary_present(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {"rsm": _RSM, "ram": _RAM}
        summary = root.find(
            "rsm:SupplyChainTradeTransaction"
            "/ram:ApplicableHeaderTradeSettlement"
            "/ram:SpecifiedTradeSettlementHeaderMonetarySummation",
            ns,
        )
        assert summary is not None
        total = summary.find("ram:GrandTotalAmount", ns)
        assert total is not None
        assert Decimal(total.text) == Decimal("121.00")

    def test_line_item_present_in_cii(self):
        xml = EN16931CIISerializer().serialize(_make_invoice())
        root = etree.fromstring(xml)
        ns = {"rsm": _RSM, "ram": _RAM}
        lines = root.findall(
            "rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem", ns
        )
        assert len(lines) == 1
        name = lines[0].find("ram:SpecifiedTradeProduct/ram:Name", ns)
        assert name.text == "Consulting services"


# ---------------------------------------------------------------------------
# CII round-trip tests
# ---------------------------------------------------------------------------

_RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"


class TestCIIRoundTrip:
    def _round_trip(self, invoice: EN16931Invoice) -> EN16931Invoice:
        xml = EN16931CIISerializer().serialize(invoice)
        return EN16931CIIParser().parse(xml)

    def test_basic_fields_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert restored.invoice_number == original.invoice_number
        assert restored.invoice_date == original.invoice_date
        assert restored.currency_code == original.currency_code
        assert restored.profile == original.profile

    def test_totals_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert restored.tax_total == original.tax_total
        assert restored.amount_due == original.amount_due
        assert restored.tax_inclusive_amount == original.tax_inclusive_amount

    def test_seller_buyer_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert restored.seller.name == original.seller.name
        assert restored.seller.vat_id == original.seller.vat_id
        assert restored.buyer.name == original.buyer.name
        assert restored.buyer.address.country_code == original.buyer.address.country_code

    def test_line_items_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert len(restored.line_items) == 1
        assert restored.line_items[0].name == original.line_items[0].name
        assert restored.line_items[0].quantity == original.line_items[0].quantity
        assert restored.line_items[0].line_net_amount == original.line_items[0].line_net_amount

    def test_tax_lines_round_trip(self):
        original = _make_invoice()
        restored = self._round_trip(original)
        assert len(restored.tax_lines) == 1
        assert restored.tax_lines[0].category == "S"
        assert restored.tax_lines[0].rate == Decimal("21")
        assert restored.tax_lines[0].tax_amount == Decimal("21.00")

    def test_note_round_trip(self):
        original = _make_invoice(note="Cross-border invoice note")
        restored = self._round_trip(original)
        assert restored.note == "Cross-border invoice note"

    def test_purchase_order_round_trip(self):
        original = _make_invoice(purchase_order_reference="PO-789")
        restored = self._round_trip(original)
        assert restored.purchase_order_reference == "PO-789"

    def test_delivery_date_round_trip(self):
        original = _make_invoice(delivery_date=date(2026, 5, 20))
        restored = self._round_trip(original)
        assert restored.delivery_date == date(2026, 5, 20)

    def test_billing_period_round_trip(self):
        original = _make_invoice(
            billing_period_start=date(2026, 5, 1),
            billing_period_end=date(2026, 5, 31),
        )
        restored = self._round_trip(original)
        assert restored.billing_period_start == date(2026, 5, 1)
        assert restored.billing_period_end == date(2026, 5, 31)

    def test_payment_means_round_trip(self):
        original = _make_invoice(
            payment_means=EN16931PaymentMeans(
                type_code="58",
                iban="IT60X0542811101000000123456",
                bic="SELBIT2B",
                account_name="Acme SA",
            )
        )
        restored = self._round_trip(original)
        assert restored.payment_means is not None
        assert restored.payment_means.iban == "IT60X0542811101000000123456"
        assert restored.payment_means.bic == "SELBIT2B"

    def test_document_allowance_round_trip(self):
        original = _make_invoice(
            allowances_charges=[
                EN16931AllowanceCharge(
                    is_charge=False,
                    amount=Decimal("5.00"),
                    reason="Discount",
                    tax_category="S",
                    tax_rate=Decimal("21"),
                )
            ]
        )
        restored = self._round_trip(original)
        assert len(restored.allowances_charges) == 1
        assert not restored.allowances_charges[0].is_charge
        assert restored.allowances_charges[0].amount == Decimal("5.00")

    def test_multi_line_multi_vat_rate(self):
        original = _make_invoice(
            sum_of_line_net_amounts=Decimal("200.00"),
            tax_exclusive_amount=Decimal("200.00"),
            tax_total=Decimal("46.00"),
            tax_inclusive_amount=Decimal("246.00"),
            amount_due=Decimal("246.00"),
            tax_lines=[
                EN16931Tax(
                    category="S",
                    rate=Decimal("21"),
                    taxable_amount=Decimal("100.00"),
                    tax_amount=Decimal("21.00"),
                ),
                EN16931Tax(
                    category="S",
                    rate=Decimal("25"),
                    taxable_amount=Decimal("100.00"),
                    tax_amount=Decimal("25.00"),
                ),
            ],
            line_items=[
                EN16931LineItem(
                    line_id="1",
                    name="Item A",
                    quantity=Decimal("1"),
                    unit_code="C62",
                    unit_price=Decimal("100.00"),
                    line_net_amount=Decimal("100.00"),
                    tax_category="S",
                    tax_rate=Decimal("21"),
                ),
                EN16931LineItem(
                    line_id="2",
                    name="Item B",
                    quantity=Decimal("2"),
                    unit_code="C62",
                    unit_price=Decimal("50.00"),
                    line_net_amount=Decimal("100.00"),
                    tax_category="S",
                    tax_rate=Decimal("25"),
                ),
            ],
        )
        restored = self._round_trip(original)
        assert len(restored.line_items) == 2
        assert len(restored.tax_lines) == 2

    def test_xml_injection_in_name_is_escaped(self):
        original = _make_invoice(
            seller=EN16931Party(
                name='<script>alert("xss")</script>',
                address=EN16931Address(
                    line_one="1 Street",
                    city="Berlin",
                    postcode="10117",
                    country_code="DE",
                ),
            )
        )
        xml = EN16931CIISerializer().serialize(original)
        assert b"<script>" not in xml
        assert b"&lt;script&gt;" in xml or b"alert" in xml


# ---------------------------------------------------------------------------
# Parser safety tests
# ---------------------------------------------------------------------------


class TestParserSafety:
    def test_ubl_parser_rejects_xxe(self):
        xxe = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
  <ID>&xxe;</ID>
</Invoice>"""
        with pytest.raises(Exception):
            EN16931UBLParser().parse(xxe)

    def test_cii_parser_rejects_xxe(self):
        xxe = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<CrossIndustryInvoice xmlns="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">
</CrossIndustryInvoice>"""
        with pytest.raises(Exception):
            EN16931CIIParser().parse(xxe)

    def test_ubl_parser_rejects_oversized(self):
        from mcp_einvoicing_core.xml_utils import MAX_XML_BYTES
        big = b"<Invoice>" + b"x" * (MAX_XML_BYTES + 1)
        with pytest.raises(ValueError, match="safety limit"):
            EN16931UBLParser().parse(big)
