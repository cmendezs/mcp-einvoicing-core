"""EN 16931 wire-format serialisers and parsers: UBL 2.1 and CII UN/CEFACT.

Provides two format families, each with a serialiser (model → XML bytes) and
a parser (XML bytes → model):

    EN16931UBLSerializer   — EN16931Invoice → UBL 2.1 Invoice / CreditNote XML
    EN16931UBLParser       — UBL 2.1 Invoice / CreditNote XML → EN16931Invoice
    EN16931CIISerializer   — EN16931Invoice → CII CrossIndustryInvoice XML
    EN16931CIIParser       — CII CrossIndustryInvoice XML → EN16931Invoice

Country packages extend these classes to add national fields:

    class ItalianUBLSerializer(EN16931UBLSerializer):
        def serialize(self, invoice: ItalianInvoice) -> bytes:
            root = self._build_root(invoice)
            # add national extensions …
            return self._to_bytes(root)

Design principles:
- All inbound XML goes through ``safe_fromstring`` (XXE/DoS protection).
- Serialisers use lxml.etree for consistent namespace handling.
- Amounts use ``format_amount`` with EN 16931 rounding rules
  (ROUND_HALF_UP for line/totals, ROUND_HALF_EVEN for VAT).
- Dates are ISO 8601 (YYYY-MM-DD) for UBL; YYYYMMDD format-102 for CII.

[Inference: BT/BG mappings derived from EN 16931-1:2017 Table 2 and cross-
 referenced against the FeRD ZUGFeRD 2.3.2 mapping guide and Peppol BIS 3.0
 spec. Verify against normative XSDs before production use.]
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Optional

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
from mcp_einvoicing_core.xml_utils import format_amount, safe_fromstring

# ---------------------------------------------------------------------------
# UBL 2.1 namespace constants
# ---------------------------------------------------------------------------

_UBL_INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
_UBL_CREDIT_NOTE_NS = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

UBL_NSMAP: dict[str, str] = {
    "cac": _CAC,
    "cbc": _CBC,
}

# ---------------------------------------------------------------------------
# CII UN/CEFACT namespace constants
# ---------------------------------------------------------------------------

_RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
_QDT = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"

CII_NSMAP: dict[str, str] = {
    "rsm": _RSM,
    "ram": _RAM,
    "udt": _UDT,
    "qdt": _QDT,
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _q(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _sub(parent: etree._Element, ns: str, local: str, text: Optional[str] = None) -> etree._Element:
    el = etree.SubElement(parent, _q(ns, local))
    if text is not None:
        el.text = text
    return el


def _sub_opt(parent: etree._Element, ns: str, local: str, text: Optional[str]) -> None:
    if text:
        _sub(parent, ns, local, text)


def _fmt(value: Decimal, rounding: str = ROUND_HALF_UP) -> str:
    return format_amount(value, rounding_mode=rounding)


def _fmt_vat(value: Decimal) -> str:
    return format_amount(value, rounding_mode=ROUND_HALF_EVEN)


def _date_ubl(d: date) -> str:
    return d.isoformat()


def _date_cii(d: date) -> str:
    return d.strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# UBL 2.1 Serialiser
# ---------------------------------------------------------------------------


class EN16931UBLSerializer:
    """Serialise an :class:`EN16931Invoice` to UBL 2.1 XML bytes.

    The root element is ``<ubl:Invoice>`` for type code 380 and
    ``<ubl:CreditNote>`` for type code 381. All other type codes
    also produce an Invoice root.

    Usage::

        xml_bytes = EN16931UBLSerializer().serialize(invoice)
    """

    def serialize(self, invoice: EN16931Invoice) -> bytes:
        root = self._build_root(invoice)
        return self._to_bytes(root)

    def _build_root(self, invoice: EN16931Invoice) -> etree._Element:
        is_credit_note = invoice.invoice_type_code == "381"
        root_local = "CreditNote" if is_credit_note else "Invoice"
        root_ns = _UBL_CREDIT_NOTE_NS if is_credit_note else _UBL_INVOICE_NS
        nsmap = {None: root_ns, **UBL_NSMAP}
        root = etree.Element(_q(root_ns, root_local), nsmap=nsmap)

        _sub(root, _CBC, "CustomizationID", invoice.profile)
        _sub(root, _CBC, "ID", invoice.invoice_number)
        _sub(root, _CBC, "IssueDate", _date_ubl(invoice.invoice_date))
        _sub(root, _CBC, "InvoiceTypeCode" if not is_credit_note else "CreditNoteTypeCode",
             invoice.invoice_type_code)
        _sub_opt(root, _CBC, "Note", invoice.note)
        _sub(root, _CBC, "DocumentCurrencyCode", invoice.currency_code)
        _sub_opt(root, _CBC, "BuyerReference", invoice.buyer_reference)

        if invoice.billing_period_start or invoice.billing_period_end:
            period = _sub(root, _CAC, "InvoicePeriod")
            if invoice.billing_period_start:
                _sub(period, _CBC, "StartDate", _date_ubl(invoice.billing_period_start))
            if invoice.billing_period_end:
                _sub(period, _CBC, "EndDate", _date_ubl(invoice.billing_period_end))

        if invoice.purchase_order_reference:
            order_ref = _sub(root, _CAC, "OrderReference")
            _sub(order_ref, _CBC, "ID", invoice.purchase_order_reference)

        if invoice.preceding_invoice_reference:
            billing_ref = _sub(root, _CAC, "BillingReference")
            inv_doc_ref = _sub(billing_ref, _CAC, "InvoiceDocumentReference")
            _sub(inv_doc_ref, _CBC, "ID", invoice.preceding_invoice_reference)
            if invoice.preceding_invoice_date:
                _sub(inv_doc_ref, _CBC, "IssueDate",
                     _date_ubl(invoice.preceding_invoice_date))

        if invoice.contract_reference:
            contract_ref = _sub(root, _CAC, "ContractDocumentReference")
            _sub(contract_ref, _CBC, "ID", invoice.contract_reference)

        if invoice.project_reference:
            proj_ref = _sub(root, _CAC, "AdditionalDocumentReference")
            _sub(proj_ref, _CBC, "ID", invoice.project_reference)

        self._build_party(root, "AccountingSupplierParty", invoice.seller)
        self._build_party(root, "AccountingCustomerParty", invoice.buyer)

        if invoice.delivery_date:
            delivery = _sub(root, _CAC, "Delivery")
            _sub(delivery, _CBC, "ActualDeliveryDate",
                 _date_ubl(invoice.delivery_date))

        if invoice.payment_means or invoice.due_date:
            self._build_payment_means(
                root,
                invoice.payment_means or EN16931PaymentMeans(type_code="1"),
                invoice.due_date,
                invoice.currency_code,
            )

        if invoice.payment_terms:
            pt = _sub(root, _CAC, "PaymentTerms")
            _sub(pt, _CBC, "Note", invoice.payment_terms)

        for ac in invoice.allowances_charges:
            self._build_allowance_charge(root, ac, invoice.currency_code)

        self._build_tax_total(root, invoice)
        self._build_monetary_total(root, invoice)

        line_tag = "CreditNoteLine" if is_credit_note else "InvoiceLine"
        for line in invoice.line_items:
            self._build_line(root, line, invoice.currency_code, line_tag, is_credit_note)

        return root

    def _build_party(self, parent: etree._Element, wrapper: str, party: EN16931Party) -> None:
        w = _sub(parent, _CAC, wrapper)
        p = _sub(w, _CAC, "Party")

        if party.electronic_address:
            ep = _sub(p, _CBC, "EndpointID", party.electronic_address)
            if party.electronic_address_scheme:
                ep.set("schemeID", party.electronic_address_scheme)

        legal = _sub(p, _CAC, "PartyLegalEntity")
        _sub(legal, _CBC, "RegistrationName", party.name)

        if party.vat_id:
            pts = _sub(p, _CAC, "PartyTaxScheme")
            _sub(pts, _CBC, "CompanyID", party.vat_id)
            ts = _sub(pts, _CAC, "TaxScheme")
            _sub(ts, _CBC, "ID", "VAT")

        self._build_address(p, party.address)

        if party.contact_name or party.contact_phone or party.contact_email:
            contact = _sub(p, _CAC, "Contact")
            _sub_opt(contact, _CBC, "Name", party.contact_name)
            _sub_opt(contact, _CBC, "Telephone", party.contact_phone)
            _sub_opt(contact, _CBC, "ElectronicMail", party.contact_email)

    def _build_address(self, parent: etree._Element, addr: EN16931Address) -> None:
        a = _sub(parent, _CAC, "PostalAddress")
        _sub(a, _CBC, "StreetName", addr.line_one)
        _sub_opt(a, _CBC, "AdditionalStreetName", addr.line_two)
        _sub(a, _CBC, "CityName", addr.city)
        _sub(a, _CBC, "PostalZone", addr.postcode)
        _sub_opt(a, _CBC, "CountrySubentity", addr.region)
        country = _sub(a, _CAC, "Country")
        _sub(country, _CBC, "IdentificationCode", addr.country_code)

    def _build_payment_means(self, parent: etree._Element, pm: EN16931PaymentMeans,
                              due_date: Optional[date], currency: str) -> None:
        el = _sub(parent, _CAC, "PaymentMeans")
        _sub(el, _CBC, "PaymentMeansCode", pm.type_code)
        if due_date:
            _sub(el, _CBC, "PaymentDueDate", _date_ubl(due_date))
        _sub_opt(el, _CBC, "PaymentID", pm.payment_id)
        if pm.iban:
            fa = _sub(el, _CAC, "PayeeFinancialAccount")
            _sub(fa, _CBC, "ID", pm.iban)
            _sub_opt(fa, _CBC, "Name", pm.account_name)
            if pm.bic:
                fib = _sub(fa, _CAC, "FinancialInstitutionBranch")
                _sub(fib, _CBC, "ID", pm.bic)
        if pm.mandate_reference:
            mandate = _sub(el, _CAC, "PaymentMandate")
            _sub(mandate, _CBC, "ID", pm.mandate_reference)
            if pm.creditor_id:
                payer = _sub(mandate, _CAC, "PayerFinancialAccount")
                _sub(payer, _CBC, "ID", pm.creditor_id)

    def _build_allowance_charge(self, parent: etree._Element, ac: EN16931AllowanceCharge,
                                 currency: str) -> None:
        el = _sub(parent, _CAC, "AllowanceCharge")
        _sub(el, _CBC, "ChargeIndicator", "true" if ac.is_charge else "false")
        _sub_opt(el, _CBC, "AllowanceChargeReasonCode", ac.reason_code)
        _sub_opt(el, _CBC, "AllowanceChargeReason", ac.reason)
        if ac.percentage is not None:
            _sub(el, _CBC, "MultiplierFactorNumeric", _fmt(ac.percentage))
        amt = _sub(el, _CBC, "Amount", _fmt(ac.amount))
        amt.set("currencyID", currency)
        if ac.base_amount is not None:
            base = _sub(el, _CBC, "BaseAmount", _fmt(ac.base_amount))
            base.set("currencyID", currency)
        tc = _sub(el, _CAC, "TaxCategory")
        _sub(tc, _CBC, "ID", ac.tax_category)
        _sub(tc, _CBC, "Percent", _fmt(ac.tax_rate))
        ts = _sub(tc, _CAC, "TaxScheme")
        _sub(ts, _CBC, "ID", "VAT")

    def _build_tax_total(self, parent: etree._Element, invoice: EN16931Invoice) -> None:
        tt = _sub(parent, _CAC, "TaxTotal")
        ta = _sub(tt, _CBC, "TaxAmount", _fmt_vat(invoice.tax_total))
        ta.set("currencyID", invoice.currency_code)
        for tl in invoice.tax_lines:
            sub = _sub(tt, _CAC, "TaxSubtotal")
            taxable = _sub(sub, _CBC, "TaxableAmount", _fmt(tl.taxable_amount))
            taxable.set("currencyID", invoice.currency_code)
            tvat = _sub(sub, _CBC, "TaxAmount", _fmt_vat(tl.tax_amount))
            tvat.set("currencyID", invoice.currency_code)
            cat = _sub(sub, _CAC, "TaxCategory")
            _sub(cat, _CBC, "ID", tl.category)
            _sub(cat, _CBC, "Percent", _fmt(tl.rate))
            _sub_opt(cat, _CBC, "TaxExemptionReasonCode", tl.exemption_reason_code)
            _sub_opt(cat, _CBC, "TaxExemptionReason", tl.exemption_reason)
            ts = _sub(cat, _CAC, "TaxScheme")
            _sub(ts, _CBC, "ID", "VAT")

    def _build_monetary_total(self, parent: etree._Element, invoice: EN16931Invoice) -> None:
        mt = _sub(parent, _CAC, "LegalMonetaryTotal")
        for tag, value in [
            ("LineExtensionAmount", invoice.sum_of_line_net_amounts),
            ("TaxExclusiveAmount", invoice.tax_exclusive_amount),
            ("TaxInclusiveAmount", invoice.tax_inclusive_amount),
            ("AllowanceTotalAmount", invoice.allowances_total),
            ("ChargeTotalAmount", invoice.charges_total),
            ("PrepaidAmount", invoice.prepaid_amount),
            ("PayableRoundingAmount", invoice.rounding_amount),
            ("PayableAmount", invoice.amount_due),
        ]:
            el = _sub(mt, _CBC, tag, _fmt(value))
            el.set("currencyID", invoice.currency_code)

    def _build_line(self, parent: etree._Element, line: EN16931LineItem,
                    currency: str, line_tag: str, is_credit_note: bool) -> None:
        el = _sub(parent, _CAC, line_tag)
        _sub(el, _CBC, "ID", line.line_id)
        qty_tag = "CreditedQuantity" if is_credit_note else "InvoicedQuantity"
        qty = _sub(el, _CBC, qty_tag, str(line.quantity))
        qty.set("unitCode", line.unit_code)
        ext = _sub(el, _CBC, "LineExtensionAmount", _fmt(line.line_net_amount))
        ext.set("currencyID", currency)
        _sub_opt(el, _CBC, "AccountingCost", line.buyer_accounting_reference)

        for ac in line.line_allowances:
            self._build_allowance_charge(el, ac, currency)

        item = _sub(el, _CAC, "Item")
        _sub_opt(item, _CBC, "Description", line.description)
        _sub(item, _CBC, "Name", line.name)
        if line.seller_article_id:
            sid = _sub(item, _CAC, "SellersItemIdentification")
            _sub(sid, _CBC, "ID", line.seller_article_id)
        if line.buyer_article_id:
            bid = _sub(item, _CAC, "BuyersItemIdentification")
            _sub(bid, _CBC, "ID", line.buyer_article_id)
        if line.standard_article_id:
            std = _sub(item, _CAC, "StandardItemIdentification")
            sid_el = _sub(std, _CBC, "ID", line.standard_article_id)
            if line.standard_article_id_scheme:
                sid_el.set("schemeID", line.standard_article_id_scheme)
        cls_tax = _sub(item, _CAC, "ClassifiedTaxCategory")
        _sub(cls_tax, _CBC, "ID", line.tax_category)
        _sub(cls_tax, _CBC, "Percent", _fmt(line.tax_rate))
        ts = _sub(cls_tax, _CAC, "TaxScheme")
        _sub(ts, _CBC, "ID", "VAT")

        price = _sub(el, _CAC, "Price")
        pa = _sub(price, _CBC, "PriceAmount", _fmt(line.unit_price, ROUND_HALF_UP))
        pa.set("currencyID", currency)
        if line.unit_price_base_quantity != Decimal("1"):
            bq = _sub(price, _CBC, "BaseQuantity", str(line.unit_price_base_quantity))
            bq.set("unitCode", line.unit_code)

    @staticmethod
    def _to_bytes(root: etree._Element, pretty_print: bool = True) -> bytes:
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=pretty_print,
        )


# ---------------------------------------------------------------------------
# UBL 2.1 Parser
# ---------------------------------------------------------------------------


class EN16931UBLParser:
    """Parse UBL 2.1 Invoice or CreditNote XML into an :class:`EN16931Invoice`.

    Only the EN 16931 core field set is extracted. National extensions are
    silently ignored; country parsers subclass this and add extraction of
    national fields.
    """

    def parse(self, xml_bytes: bytes) -> EN16931Invoice:
        root = safe_fromstring(xml_bytes)
        return self._extract(root)

    def _extract(self, root: etree._Element) -> EN16931Invoice:
        local = etree.QName(root.tag).localname
        is_credit_note = local == "CreditNote"

        def txt(el: Optional[etree._Element]) -> Optional[str]:
            return el.text.strip() if el is not None and el.text else None

        def find(xpath: str) -> Optional[etree._Element]:
            results = root.xpath(xpath, namespaces={"cbc": _CBC, "cac": _CAC})
            return results[0] if results else None  # type: ignore[return-value]

        def findall(xpath: str) -> list[etree._Element]:
            return root.xpath(xpath, namespaces={"cbc": _CBC, "cac": _CAC})  # type: ignore[return-value]

        def get_text(xpath: str) -> Optional[str]:
            return txt(find(xpath))

        def get_decimal(xpath: str, default: Decimal = Decimal("0")) -> Decimal:
            v = get_text(xpath)
            return Decimal(v) if v else default

        profile = get_text("cbc:CustomizationID") or ""
        invoice_number = get_text("cbc:ID") or ""
        issue_date_str = get_text("cbc:IssueDate") or ""
        issue_date = date.fromisoformat(issue_date_str) if issue_date_str else date.today()
        type_code = get_text("cbc:InvoiceTypeCode") or get_text("cbc:CreditNoteTypeCode") or (
            "381" if is_credit_note else "380"
        )
        currency = get_text("cbc:DocumentCurrencyCode") or "EUR"

        seller = self._parse_party(find("cac:AccountingSupplierParty/cac:Party"))
        buyer = self._parse_party(find("cac:AccountingCustomerParty/cac:Party"))

        tax_lines = [self._parse_tax_subtotal(s) for s in findall("cac:TaxTotal/cac:TaxSubtotal")]

        mt_prefix = "cac:LegalMonetaryTotal"
        sum_lines = get_decimal(f"{mt_prefix}/cbc:LineExtensionAmount")
        tax_excl = get_decimal(f"{mt_prefix}/cbc:TaxExclusiveAmount")
        tax_incl = get_decimal(f"{mt_prefix}/cbc:TaxInclusiveAmount")
        allowances_total = get_decimal(f"{mt_prefix}/cbc:AllowanceTotalAmount")
        charges_total = get_decimal(f"{mt_prefix}/cbc:ChargeTotalAmount")
        prepaid = get_decimal(f"{mt_prefix}/cbc:PrepaidAmount")
        rounding = get_decimal(f"{mt_prefix}/cbc:PayableRoundingAmount")
        amount_due = get_decimal(f"{mt_prefix}/cbc:PayableAmount")
        tax_total = get_decimal("cac:TaxTotal/cbc:TaxAmount")

        line_tag = "cac:CreditNoteLine" if is_credit_note else "cac:InvoiceLine"
        line_items = [self._parse_line(le, is_credit_note) for le in findall(line_tag)]

        payment_means = None
        pm_el = find("cac:PaymentMeans")
        if pm_el is not None:
            payment_means = self._parse_payment_means(pm_el)

        billing_start: Optional[date] = None
        billing_end: Optional[date] = None
        period_el = find("cac:InvoicePeriod")
        if period_el is not None:
            s = txt(period_el.find(_q(_CBC, "StartDate")))
            e = txt(period_el.find(_q(_CBC, "EndDate")))
            if s:
                billing_start = date.fromisoformat(s)
            if e:
                billing_end = date.fromisoformat(e)

        preceding_ref = get_text(
            "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID"
        )
        preceding_date_str = get_text(
            "cac:BillingReference/cac:InvoiceDocumentReference/cbc:IssueDate"
        )
        preceding_date: Optional[date] = (
            date.fromisoformat(preceding_date_str) if preceding_date_str else None
        )
        delivery_date_str = get_text("cac:Delivery/cbc:ActualDeliveryDate")
        delivery_date: Optional[date] = (
            date.fromisoformat(delivery_date_str) if delivery_date_str else None
        )
        due_date_str = get_text("cac:PaymentMeans/cbc:PaymentDueDate")
        due_date: Optional[date] = (
            date.fromisoformat(due_date_str) if due_date_str else None
        )

        allowances_charges = [
            self._parse_allowance_charge(ac_el) for ac_el in findall("cac:AllowanceCharge")
        ]

        return EN16931Invoice(
            profile=profile,
            invoice_number=invoice_number,
            invoice_date=issue_date,
            invoice_type_code=type_code,
            currency_code=currency,
            note=get_text("cbc:Note"),
            buyer_reference=get_text("cbc:BuyerReference"),
            purchase_order_reference=get_text("cac:OrderReference/cbc:ID"),
            contract_reference=get_text("cac:ContractDocumentReference/cbc:ID"),
            project_reference=get_text("cac:AdditionalDocumentReference/cbc:ID"),
            billing_period_start=billing_start,
            billing_period_end=billing_end,
            delivery_date=delivery_date,
            seller=seller,
            buyer=buyer,
            sum_of_line_net_amounts=sum_lines,
            allowances_total=allowances_total,
            charges_total=charges_total,
            tax_exclusive_amount=tax_excl,
            tax_total=tax_total,
            tax_inclusive_amount=tax_incl,
            prepaid_amount=prepaid,
            rounding_amount=rounding,
            amount_due=amount_due,
            tax_lines=tax_lines,
            allowances_charges=allowances_charges,
            payment_means=payment_means,
            payment_terms=get_text("cac:PaymentTerms/cbc:Note"),
            due_date=due_date,
            line_items=line_items,
            preceding_invoice_reference=preceding_ref,
            preceding_invoice_date=preceding_date,
        )

    def _parse_party(self, el: Optional[etree._Element]) -> EN16931Party:
        if el is None:
            return EN16931Party(
                name="",
                address=EN16931Address(
                    line_one="", city="", postcode="", country_code="XX"
                ),
            )

        def txt(tag_el: Optional[etree._Element]) -> Optional[str]:
            return tag_el.text.strip() if tag_el is not None and tag_el.text else None

        name = txt(el.find(".//" + _q(_CBC, "RegistrationName")))
        vat_id = txt(el.find(".//" + _q(_CBC, "CompanyID")))
        ep_el = el.find(_q(_CBC, "EndpointID"))
        endpoint = txt(ep_el)
        scheme = ep_el.get("schemeID") if ep_el is not None else None

        addr_el = el.find(".//" + _q(_CAC, "PostalAddress"))
        address = self._parse_address(addr_el)

        contact_el = el.find(_q(_CAC, "Contact"))
        contact_name = contact_phone = contact_email = None
        if contact_el is not None:
            contact_name = txt(contact_el.find(_q(_CBC, "Name")))
            contact_phone = txt(contact_el.find(_q(_CBC, "Telephone")))
            contact_email = txt(contact_el.find(_q(_CBC, "ElectronicMail")))

        return EN16931Party(
            name=name or "",
            address=address,
            vat_id=vat_id,
            electronic_address=endpoint,
            electronic_address_scheme=scheme,
            contact_name=contact_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
        )

    def _parse_address(self, el: Optional[etree._Element]) -> EN16931Address:
        if el is None:
            return EN16931Address(line_one="", city="", postcode="", country_code="XX")

        def txt(tag_el: Optional[etree._Element]) -> Optional[str]:
            return tag_el.text.strip() if tag_el is not None and tag_el.text else None

        return EN16931Address(
            line_one=txt(el.find(_q(_CBC, "StreetName"))) or "",
            line_two=txt(el.find(_q(_CBC, "AdditionalStreetName"))),
            city=txt(el.find(_q(_CBC, "CityName"))) or "",
            postcode=txt(el.find(_q(_CBC, "PostalZone"))) or "",
            region=txt(el.find(_q(_CBC, "CountrySubentity"))),
            country_code=txt(el.find(".//" + _q(_CBC, "IdentificationCode"))) or "XX",
        )

    def _parse_tax_subtotal(self, el: etree._Element) -> EN16931Tax:
        def txt(tag: str) -> Optional[str]:
            found = el.find(".//" + _q(_CBC, tag))
            return found.text.strip() if found is not None and found.text else None

        def amount(tag: str) -> Decimal:
            found = el.find(_q(_CBC, tag))
            if found is not None and found.text:
                return Decimal(found.text.strip())
            return Decimal("0")

        return EN16931Tax(
            category=txt("ID") or "S",
            rate=Decimal(txt("Percent") or "0"),
            taxable_amount=amount("TaxableAmount"),
            tax_amount=amount("TaxAmount"),
            exemption_reason=txt("TaxExemptionReason"),
            exemption_reason_code=txt("TaxExemptionReasonCode"),
        )

    def _parse_payment_means(self, el: etree._Element) -> EN16931PaymentMeans:
        def txt(tag: str) -> Optional[str]:
            found = el.find(_q(_CBC, tag))
            return found.text.strip() if found is not None and found.text else None

        fa = el.find(_q(_CAC, "PayeeFinancialAccount"))
        iban = None
        bic = None
        account_name = None
        if fa is not None:
            iban = (fa.find(_q(_CBC, "ID")) or fa).text  # type: ignore[union-attr]
            if fa.find(_q(_CBC, "ID")) is not None:
                iban = fa.find(_q(_CBC, "ID")).text  # type: ignore[union-attr]
                iban = iban.strip() if iban else None
            name_el = fa.find(_q(_CBC, "Name"))
            account_name = name_el.text.strip() if name_el is not None and name_el.text else None
            fib = fa.find(_q(_CAC, "FinancialInstitutionBranch"))
            if fib is not None:
                bic_el = fib.find(_q(_CBC, "ID"))
                bic = bic_el.text.strip() if bic_el is not None and bic_el.text else None

        mandate_ref = None
        creditor_id = None
        mandate_el = el.find(_q(_CAC, "PaymentMandate"))
        if mandate_el is not None:
            id_el = mandate_el.find(_q(_CBC, "ID"))
            mandate_ref = id_el.text.strip() if id_el is not None and id_el.text else None
            payer_el = mandate_el.find(_q(_CAC, "PayerFinancialAccount"))
            if payer_el is not None:
                pid = payer_el.find(_q(_CBC, "ID"))
                creditor_id = pid.text.strip() if pid is not None and pid.text else None

        return EN16931PaymentMeans(
            type_code=txt("PaymentMeansCode") or "30",
            payment_id=txt("PaymentID"),
            iban=iban,
            bic=bic,
            account_name=account_name,
            mandate_reference=mandate_ref,
            creditor_id=creditor_id,
        )

    def _parse_allowance_charge(self, el: etree._Element) -> EN16931AllowanceCharge:
        def txt(tag: str) -> Optional[str]:
            found = el.find(_q(_CBC, tag))
            return found.text.strip() if found is not None and found.text else None

        is_charge = (txt("ChargeIndicator") or "false").lower() == "true"
        amount_el = el.find(_q(_CBC, "Amount"))
        amount = Decimal(amount_el.text or "0") if amount_el is not None else Decimal("0")
        base_el = el.find(_q(_CBC, "BaseAmount"))
        base_amount = Decimal(base_el.text or "0") if base_el is not None else None
        pct_el = el.find(_q(_CBC, "MultiplierFactorNumeric"))
        percentage = Decimal(pct_el.text or "0") if pct_el is not None else None
        tc = el.find(".//" + _q(_CBC, "ID"))
        tax_category = tc.text.strip() if tc is not None and tc.text else "S"
        tp_el = el.find(".//" + _q(_CBC, "Percent"))
        tax_rate = Decimal(tp_el.text or "0") if tp_el is not None else Decimal("0")

        return EN16931AllowanceCharge(
            is_charge=is_charge,
            amount=amount,
            base_amount=base_amount,
            percentage=percentage,
            reason=txt("AllowanceChargeReason"),
            reason_code=txt("AllowanceChargeReasonCode"),
            tax_category=tax_category,
            tax_rate=tax_rate,
        )

    def _parse_line(self, el: etree._Element, is_credit_note: bool) -> EN16931LineItem:
        def txt(tag: str) -> Optional[str]:
            found = el.find(_q(_CBC, tag))
            return found.text.strip() if found is not None and found.text else None

        def txt_nested(xpath: str) -> Optional[str]:
            results = el.xpath(xpath, namespaces={"cbc": _CBC, "cac": _CAC})
            if results and results[0].text:
                return results[0].text.strip()
            return None

        qty_tag = "CreditedQuantity" if is_credit_note else "InvoicedQuantity"
        qty_el = el.find(_q(_CBC, qty_tag))
        quantity = Decimal(qty_el.text or "1") if qty_el is not None else Decimal("1")
        unit_code = qty_el.get("unitCode", "C62") if qty_el is not None else "C62"

        ext_el = el.find(_q(_CBC, "LineExtensionAmount"))
        line_net = Decimal(ext_el.text or "0") if ext_el is not None else Decimal("0")

        price_el = el.find(_q(_CAC, "Price"))
        unit_price = Decimal("0")
        unit_price_base = Decimal("1")
        if price_el is not None:
            pa = price_el.find(_q(_CBC, "PriceAmount"))
            unit_price = Decimal(pa.text or "0") if pa is not None else Decimal("0")
            bq = price_el.find(_q(_CBC, "BaseQuantity"))
            if bq is not None:
                unit_price_base = Decimal(bq.text or "1")

        item_el = el.find(_q(_CAC, "Item"))
        name = ""
        description = None
        seller_id = buyer_id = std_id = std_scheme = None
        tax_category = "S"
        tax_rate = Decimal("0")
        if item_el is not None:
            n = item_el.find(_q(_CBC, "Name"))
            name = n.text.strip() if n is not None and n.text else ""
            d = item_el.find(_q(_CBC, "Description"))
            description = d.text.strip() if d is not None and d.text else None
            s_id = item_el.find(_q(_CAC, "SellersItemIdentification"))
            if s_id is not None:
                id_el = s_id.find(_q(_CBC, "ID"))
                seller_id = id_el.text.strip() if id_el is not None and id_el.text else None
            b_id = item_el.find(_q(_CAC, "BuyersItemIdentification"))
            if b_id is not None:
                id_el = b_id.find(_q(_CBC, "ID"))
                buyer_id = id_el.text.strip() if id_el is not None and id_el.text else None
            std = item_el.find(_q(_CAC, "StandardItemIdentification"))
            if std is not None:
                id_el = std.find(_q(_CBC, "ID"))
                if id_el is not None:
                    std_id = id_el.text.strip() if id_el.text else None
                    std_scheme = id_el.get("schemeID")
            cls_tax = item_el.find(_q(_CAC, "ClassifiedTaxCategory"))
            if cls_tax is not None:
                cat_el = cls_tax.find(_q(_CBC, "ID"))
                tax_category = cat_el.text.strip() if cat_el is not None and cat_el.text else "S"
                pct = cls_tax.find(_q(_CBC, "Percent"))
                tax_rate = Decimal(pct.text or "0") if pct is not None else Decimal("0")

        line_allowances = [
            self._parse_allowance_charge(ac_el)
            for ac_el in el.findall(_q(_CAC, "AllowanceCharge"))
        ]

        return EN16931LineItem(
            line_id=txt("ID") or "1",
            name=name,
            description=description,
            quantity=quantity,
            unit_code=unit_code,
            unit_price=unit_price,
            unit_price_base_quantity=unit_price_base,
            line_net_amount=line_net,
            tax_category=tax_category,
            tax_rate=tax_rate,
            buyer_accounting_reference=txt("AccountingCost"),
            seller_article_id=seller_id,
            buyer_article_id=buyer_id,
            standard_article_id=std_id,
            standard_article_id_scheme=std_scheme,
            line_allowances=line_allowances,
        )


# ---------------------------------------------------------------------------
# CII Serialiser
# ---------------------------------------------------------------------------


class EN16931CIISerializer:
    """Serialise an :class:`EN16931Invoice` to CII UN/CEFACT XML bytes.

    Produces a ``<rsm:CrossIndustryInvoice>`` document conforming to the
    CII D16B schema, compatible with ZUGFeRD 2.x and Factur-X profiles.

    Usage::

        xml_bytes = EN16931CIISerializer().serialize(invoice)
    """

    def serialize(self, invoice: EN16931Invoice) -> bytes:
        root = self._build_root(invoice)
        return self._to_bytes(root)

    def _build_root(self, invoice: EN16931Invoice) -> etree._Element:
        root = etree.Element(_q(_RSM, "CrossIndustryInvoice"), nsmap=CII_NSMAP)

        # ExchangedDocumentContext — profile URN (BT-24)
        ctx = _sub(root, _RSM, "ExchangedDocumentContext")
        guideline = _sub(ctx, _RAM, "GuidelineSpecifiedDocumentContextParameter")
        _sub(guideline, _RAM, "ID", invoice.profile)

        # ExchangedDocument — invoice header
        doc = _sub(root, _RSM, "ExchangedDocument")
        _sub(doc, _RAM, "ID", invoice.invoice_number)
        _sub(doc, _RAM, "TypeCode", invoice.invoice_type_code)
        idt = _sub(doc, _RAM, "IssueDateTime")
        dt_str = _sub(idt, _UDT, "DateTimeString", _date_cii(invoice.invoice_date))
        dt_str.set("format", "102")
        if invoice.note:
            note_el = _sub(doc, _RAM, "IncludedNote")
            _sub(note_el, _RAM, "Content", invoice.note)

        # SupplyChainTradeTransaction
        txn = _sub(root, _RSM, "SupplyChainTradeTransaction")

        # Line items
        for line in invoice.line_items:
            self._build_line(txn, line, invoice.currency_code)

        # ApplicableHeaderTradeAgreement
        agreement = _sub(txn, _RAM, "ApplicableHeaderTradeAgreement")
        _sub_opt(agreement, _RAM, "BuyerReference", invoice.buyer_reference)
        self._build_party_cii(agreement, "SellerTradeParty", invoice.seller)
        self._build_party_cii(agreement, "BuyerTradeParty", invoice.buyer)
        if invoice.purchase_order_reference:
            order = _sub(agreement, _RAM, "BuyerOrderReferencedDocument")
            _sub(order, _RAM, "IssuerAssignedID", invoice.purchase_order_reference)
        if invoice.contract_reference:
            contract = _sub(agreement, _RAM, "ContractReferencedDocument")
            _sub(contract, _RAM, "IssuerAssignedID", invoice.contract_reference)
        if invoice.project_reference:
            proj = _sub(agreement, _RAM, "SpecifiedProcuringProject")
            _sub(proj, _RAM, "ID", invoice.project_reference)
        if invoice.preceding_invoice_reference:
            prec = _sub(agreement, _RAM, "InvoiceReferencedDocument")
            _sub(prec, _RAM, "IssuerAssignedID", invoice.preceding_invoice_reference)
            if invoice.preceding_invoice_date:
                prec_dt = _sub(prec, _RAM, "FormattedIssueDateTime")
                dt = _sub(prec_dt, _QDT, "DateTimeString",
                          _date_cii(invoice.preceding_invoice_date))
                dt.set("format", "102")

        # ApplicableHeaderTradeDelivery
        delivery = _sub(txn, _RAM, "ApplicableHeaderTradeDelivery")
        if invoice.delivery_date:
            evt = _sub(delivery, _RAM, "ActualDeliverySupplyChainEvent")
            occ = _sub(evt, _RAM, "OccurrenceDateTime")
            dt = _sub(occ, _UDT, "DateTimeString", _date_cii(invoice.delivery_date))
            dt.set("format", "102")
        if invoice.billing_period_start or invoice.billing_period_end:
            period = _sub(delivery, _RAM, "DeliverySpecifiedPeriod")
            if invoice.billing_period_start:
                start = _sub(period, _RAM, "StartDateTime")
                dt = _sub(start, _UDT, "DateTimeString",
                          _date_cii(invoice.billing_period_start))
                dt.set("format", "102")
            if invoice.billing_period_end:
                end = _sub(period, _RAM, "EndDateTime")
                dt = _sub(end, _UDT, "DateTimeString",
                          _date_cii(invoice.billing_period_end))
                dt.set("format", "102")

        # ApplicableHeaderTradeSettlement
        settlement = _sub(txn, _RAM, "ApplicableHeaderTradeSettlement")
        if invoice.payment_means and invoice.payment_means.payment_id:
            _sub(settlement, _RAM, "PaymentReference",
                 invoice.payment_means.payment_id)
        _sub(settlement, _RAM, "InvoiceCurrencyCode", invoice.currency_code)

        if invoice.payment_means:
            self._build_payment_means_cii(settlement, invoice.payment_means)

        for tl in invoice.tax_lines:
            self._build_tax_cii(settlement, tl)

        for ac in invoice.allowances_charges:
            self._build_allowance_charge_cii(settlement, ac, invoice.currency_code)

        if invoice.payment_terms or invoice.due_date:
            pt = _sub(settlement, _RAM, "SpecifiedTradePaymentTerms")
            _sub_opt(pt, _RAM, "Description", invoice.payment_terms)
            if invoice.due_date:
                due = _sub(pt, _RAM, "DueDateDateTime")
                dt = _sub(due, _UDT, "DateTimeString", _date_cii(invoice.due_date))
                dt.set("format", "102")

        self._build_monetary_summary(settlement, invoice)
        return root

    def _build_party_cii(self, parent: etree._Element, tag: str,
                          party: EN16931Party) -> None:
        p = _sub(parent, _RAM, tag)
        _sub(p, _RAM, "Name", party.name)
        if party.vat_id:
            tax_reg = _sub(p, _RAM, "SpecifiedTaxRegistration")
            id_el = _sub(tax_reg, _RAM, "ID", party.vat_id)
            id_el.set("schemeID", "VA")
        if party.electronic_address:
            ep = _sub(p, _RAM, "URIUniversalCommunication")
            uri = _sub(ep, _RAM, "URIID", party.electronic_address)
            if party.electronic_address_scheme:
                uri.set("schemeID", party.electronic_address_scheme)
        addr = party.address
        postal = _sub(p, _RAM, "PostalTradeAddress")
        _sub(postal, _RAM, "PostcodeCode", addr.postcode)
        _sub(postal, _RAM, "LineOne", addr.line_one)
        _sub_opt(postal, _RAM, "LineTwo", addr.line_two)
        _sub(postal, _RAM, "CityName", addr.city)
        _sub(postal, _RAM, "CountryID", addr.country_code)
        _sub_opt(postal, _RAM, "CountrySubDivisionName", addr.region)

        if party.contact_name or party.contact_phone or party.contact_email:
            contact = _sub(p, _RAM, "DefinedTradeContact")
            _sub_opt(contact, _RAM, "PersonName", party.contact_name)
            if party.contact_phone:
                ph = _sub(contact, _RAM, "TelephoneUniversalCommunication")
                _sub(ph, _RAM, "CompleteNumber", party.contact_phone)
            if party.contact_email:
                em = _sub(contact, _RAM, "EmailURIUniversalCommunication")
                _sub(em, _RAM, "URIID", party.contact_email)

    def _build_payment_means_cii(self, parent: etree._Element,
                                  pm: EN16931PaymentMeans) -> None:
        el = _sub(parent, _RAM, "SpecifiedTradeSettlementPaymentMeans")
        _sub(el, _RAM, "TypeCode", pm.type_code)
        if pm.iban:
            acc = _sub(el, _RAM, "PayeePartyCreditorFinancialAccount")
            _sub(acc, _RAM, "IBANID", pm.iban)
            if pm.account_name:
                _sub(acc, _RAM, "AccountName", pm.account_name)
        if pm.bic:
            fi = _sub(el, _RAM, "PayeeSpecifiedCreditorFinancialInstitution")
            _sub(fi, _RAM, "BICID", pm.bic)

    def _build_tax_cii(self, parent: etree._Element, tl: EN16931Tax) -> None:
        tax = _sub(parent, _RAM, "ApplicableTradeTax")
        ta = _sub(tax, _RAM, "CalculatedAmount", _fmt_vat(tl.tax_amount))
        ta.set("currencyID", "")  # currencyID omitted at line level per CII
        _sub(tax, _RAM, "TypeCode", "VAT")
        _sub_opt(tax, _RAM, "ExemptionReason", tl.exemption_reason)
        _sub_opt(tax, _RAM, "ExemptionReasonCode", tl.exemption_reason_code)
        base = _sub(tax, _RAM, "BasisAmount", _fmt(tl.taxable_amount))
        base.set("currencyID", "")
        _sub(tax, _RAM, "CategoryCode", tl.category)
        _sub(tax, _RAM, "RateApplicablePercent", _fmt(tl.rate))

    def _build_allowance_charge_cii(self, parent: etree._Element,
                                     ac: EN16931AllowanceCharge,
                                     currency: str) -> None:
        el = _sub(parent, _RAM, "SpecifiedTradeAllowanceCharge")
        _sub(el, _RAM, "ChargeIndicator",
             "true" if ac.is_charge else "false")
        if ac.percentage is not None:
            _sub(el, _RAM, "CalculationPercent", _fmt(ac.percentage))
        if ac.base_amount is not None:
            base = _sub(el, _RAM, "BasisAmount", _fmt(ac.base_amount))
            base.set("currencyID", currency)
        amt = _sub(el, _RAM, "ActualAmount", _fmt(ac.amount))
        amt.set("currencyID", currency)
        _sub_opt(el, _RAM, "ReasonCode", ac.reason_code)
        _sub_opt(el, _RAM, "Reason", ac.reason)
        tc = _sub(el, _RAM, "CategoryTradeTax")
        _sub(tc, _RAM, "TypeCode", "VAT")
        _sub(tc, _RAM, "CategoryCode", ac.tax_category)
        _sub(tc, _RAM, "RateApplicablePercent", _fmt(ac.tax_rate))

    def _build_monetary_summary(self, parent: etree._Element,
                                 invoice: EN16931Invoice) -> None:
        s = _sub(parent, _RAM, "SpecifiedTradeSettlementHeaderMonetarySummation")
        for tag, val, rounding in [
            ("LineTotalAmount", invoice.sum_of_line_net_amounts, ROUND_HALF_UP),
            ("ChargeTotalAmount", invoice.charges_total, ROUND_HALF_UP),
            ("AllowanceTotalAmount", invoice.allowances_total, ROUND_HALF_UP),
            ("TaxBasisTotalAmount", invoice.tax_exclusive_amount, ROUND_HALF_UP),
            ("TaxTotalAmount", invoice.tax_total, ROUND_HALF_EVEN),
            ("GrandTotalAmount", invoice.tax_inclusive_amount, ROUND_HALF_UP),
            ("TotalPrepaidAmount", invoice.prepaid_amount, ROUND_HALF_UP),
            ("DuePayableAmount", invoice.amount_due, ROUND_HALF_UP),
        ]:
            _sub(s, _RAM, tag, format_amount(val, rounding_mode=rounding))

    def _build_line(self, parent: etree._Element, line: EN16931LineItem,
                    currency: str) -> None:
        el = _sub(parent, _RAM, "IncludedSupplyChainTradeLineItem")
        doc = _sub(el, _RAM, "AssociatedDocumentLineDocument")
        _sub(doc, _RAM, "LineID", line.line_id)

        product = _sub(el, _RAM, "SpecifiedTradeProduct")
        if line.seller_article_id:
            _sub(product, _RAM, "SellerAssignedID", line.seller_article_id)
        if line.buyer_article_id:
            _sub(product, _RAM, "BuyerAssignedID", line.buyer_article_id)
        if line.standard_article_id:
            gid = _sub(product, _RAM, "GlobalID", line.standard_article_id)
            if line.standard_article_id_scheme:
                gid.set("schemeID", line.standard_article_id_scheme)
        _sub(product, _RAM, "Name", line.name)
        _sub_opt(product, _RAM, "Description", line.description)

        agreement = _sub(el, _RAM, "SpecifiedLineTradeAgreement")
        net_price = _sub(agreement, _RAM, "NetPriceProductTradePrice")
        charge_amt = _sub(net_price, _RAM, "ChargeAmount",
                          _fmt(line.unit_price, ROUND_HALF_UP))
        charge_amt.set("currencyID", currency)
        if line.unit_price_base_quantity != Decimal("1"):
            bq = _sub(net_price, _RAM, "BasisQuantity",
                      str(line.unit_price_base_quantity))
            bq.set("unitCode", line.unit_code)

        delivery = _sub(el, _RAM, "SpecifiedLineTradeDelivery")
        qty = _sub(delivery, _RAM, "BilledQuantity", str(line.quantity))
        qty.set("unitCode", line.unit_code)

        settlement = _sub(el, _RAM, "SpecifiedLineTradeSettlement")
        if line.buyer_accounting_reference:
            _sub(settlement, _RAM, "ReceivableSpecifiedTradeAccountingAccount",
                 line.buyer_accounting_reference)
        tax = _sub(settlement, _RAM, "ApplicableTradeTax")
        _sub(tax, _RAM, "TypeCode", "VAT")
        _sub(tax, _RAM, "CategoryCode", line.tax_category)
        _sub(tax, _RAM, "RateApplicablePercent", _fmt(line.tax_rate))

        for ac in line.line_allowances:
            self._build_allowance_charge_cii(settlement, ac, currency)

        total = _sub(settlement, _RAM, "SpecifiedTradeSettlementLineMonetarySummation")
        la = _sub(total, _RAM, "LineTotalAmount", _fmt(line.line_net_amount))
        la.set("currencyID", currency)

    @staticmethod
    def _to_bytes(root: etree._Element, pretty_print: bool = True) -> bytes:
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=pretty_print,
        )


# ---------------------------------------------------------------------------
# CII Parser
# ---------------------------------------------------------------------------


class EN16931CIIParser:
    """Parse CII UN/CEFACT CrossIndustryInvoice XML into an :class:`EN16931Invoice`.

    Covers the EN 16931 core field set. ZUGFeRD / Factur-X national extensions
    are silently ignored; country parsers subclass and add extraction logic.
    """

    def parse(self, xml_bytes: bytes) -> EN16931Invoice:
        root = safe_fromstring(xml_bytes)
        return self._extract(root)

    def _extract(self, root: etree._Element) -> EN16931Invoice:
        ns = {"rsm": _RSM, "ram": _RAM, "udt": _UDT, "qdt": _QDT}

        def xpath_txt(path: str) -> Optional[str]:
            results = root.xpath(path + "/text()", namespaces=ns)
            return str(results[0]).strip() if results else None

        def xpath_els(path: str) -> list[etree._Element]:
            return root.xpath(path, namespaces=ns)  # type: ignore[return-value]

        def xpath_el(path: str) -> Optional[etree._Element]:
            r = xpath_els(path)
            return r[0] if r else None

        profile = xpath_txt("rsm:ExchangedDocumentContext"
                            "/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID") or ""
        invoice_number = xpath_txt("rsm:ExchangedDocument/ram:ID") or ""
        type_code = xpath_txt("rsm:ExchangedDocument/ram:TypeCode") or "380"

        date_str = xpath_txt(
            "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString"
        ) or ""
        invoice_date = (
            date.fromisoformat(f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}")
            if len(date_str) == 8 else date.today()
        )

        note_el = xpath_el("rsm:ExchangedDocument/ram:IncludedNote/ram:Content")
        note = note_el.text.strip() if note_el is not None and note_el.text else None

        txn = "rsm:SupplyChainTradeTransaction"
        agreement = f"{txn}/ram:ApplicableHeaderTradeAgreement"
        delivery_path = f"{txn}/ram:ApplicableHeaderTradeDelivery"
        settlement = f"{txn}/ram:ApplicableHeaderTradeSettlement"

        currency = xpath_txt(f"{settlement}/ram:InvoiceCurrencyCode") or "EUR"
        buyer_reference = xpath_txt(f"{agreement}/ram:BuyerReference")

        seller_el = xpath_el(f"{agreement}/ram:SellerTradeParty")
        buyer_el = xpath_el(f"{agreement}/ram:BuyerTradeParty")
        seller = self._parse_party_cii(seller_el)
        buyer = self._parse_party_cii(buyer_el)

        purchase_order = xpath_txt(
            f"{agreement}/ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID"
        )
        contract_ref = xpath_txt(
            f"{agreement}/ram:ContractReferencedDocument/ram:IssuerAssignedID"
        )
        project_ref = xpath_txt(
            f"{agreement}/ram:SpecifiedProcuringProject/ram:ID"
        )
        preceding_ref = xpath_txt(
            f"{agreement}/ram:InvoiceReferencedDocument/ram:IssuerAssignedID"
        )
        preceding_date_str = xpath_txt(
            f"{agreement}/ram:InvoiceReferencedDocument"
            "/ram:FormattedIssueDateTime/qdt:DateTimeString"
        )
        preceding_date: Optional[date] = None
        if preceding_date_str and len(preceding_date_str) == 8:
            preceding_date = date.fromisoformat(
                f"{preceding_date_str[:4]}-{preceding_date_str[4:6]}-{preceding_date_str[6:]}"
            )

        delivery_date: Optional[date] = None
        delivery_str = xpath_txt(
            f"{delivery_path}/ram:ActualDeliverySupplyChainEvent"
            "/ram:OccurrenceDateTime/udt:DateTimeString"
        )
        if delivery_str and len(delivery_str) == 8:
            delivery_date = date.fromisoformat(
                f"{delivery_str[:4]}-{delivery_str[4:6]}-{delivery_str[6:]}"
            )

        billing_start: Optional[date] = None
        billing_end: Optional[date] = None
        period_start_str = xpath_txt(
            f"{delivery_path}/ram:DeliverySpecifiedPeriod/ram:StartDateTime/udt:DateTimeString"
        )
        period_end_str = xpath_txt(
            f"{delivery_path}/ram:DeliverySpecifiedPeriod/ram:EndDateTime/udt:DateTimeString"
        )
        if period_start_str and len(period_start_str) == 8:
            billing_start = date.fromisoformat(
                f"{period_start_str[:4]}-{period_start_str[4:6]}-{period_start_str[6:]}"
            )
        if period_end_str and len(period_end_str) == 8:
            billing_end = date.fromisoformat(
                f"{period_end_str[:4]}-{period_end_str[4:6]}-{period_end_str[6:]}"
            )

        payment_means = None
        pm_el = xpath_el(f"{settlement}/ram:SpecifiedTradeSettlementPaymentMeans")
        if pm_el is not None:
            payment_means = self._parse_payment_means_cii(pm_el)

        payment_terms_txt = xpath_txt(
            f"{settlement}/ram:SpecifiedTradePaymentTerms/ram:Description"
        )
        due_str = xpath_txt(
            f"{settlement}/ram:SpecifiedTradePaymentTerms"
            "/ram:DueDateDateTime/udt:DateTimeString"
        )
        due_date: Optional[date] = None
        if due_str and len(due_str) == 8:
            due_date = date.fromisoformat(
                f"{due_str[:4]}-{due_str[4:6]}-{due_str[6:]}"
            )

        tax_lines = [
            self._parse_tax_cii(t)
            for t in xpath_els(f"{settlement}/ram:ApplicableTradeTax")
        ]

        allowances_charges = [
            self._parse_allowance_charge_cii(ac)
            for ac in xpath_els(f"{settlement}/ram:SpecifiedTradeAllowanceCharge")
        ]

        def dec(path: str, default: str = "0") -> Decimal:
            v = xpath_txt(path)
            return Decimal(v) if v else Decimal(default)

        summary = f"{settlement}/ram:SpecifiedTradeSettlementHeaderMonetarySummation"
        sum_lines = dec(f"{summary}/ram:LineTotalAmount")
        charges_total = dec(f"{summary}/ram:ChargeTotalAmount")
        allowances_total = dec(f"{summary}/ram:AllowanceTotalAmount")
        tax_excl = dec(f"{summary}/ram:TaxBasisTotalAmount")
        tax_total = dec(f"{summary}/ram:TaxTotalAmount")
        tax_incl = dec(f"{summary}/ram:GrandTotalAmount")
        prepaid = dec(f"{summary}/ram:TotalPrepaidAmount")
        amount_due = dec(f"{summary}/ram:DuePayableAmount")

        line_items = [
            self._parse_line_cii(le)
            for le in xpath_els(
                f"{txn}/ram:IncludedSupplyChainTradeLineItem"
            )
        ]

        return EN16931Invoice(
            profile=profile,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            invoice_type_code=type_code,
            currency_code=currency,
            note=note,
            buyer_reference=buyer_reference,
            purchase_order_reference=purchase_order,
            contract_reference=contract_ref,
            project_reference=project_ref,
            billing_period_start=billing_start,
            billing_period_end=billing_end,
            delivery_date=delivery_date,
            seller=seller,
            buyer=buyer,
            sum_of_line_net_amounts=sum_lines,
            allowances_total=allowances_total,
            charges_total=charges_total,
            tax_exclusive_amount=tax_excl,
            tax_total=tax_total,
            tax_inclusive_amount=tax_incl,
            prepaid_amount=prepaid,
            rounding_amount=Decimal("0"),
            amount_due=amount_due,
            tax_lines=tax_lines,
            allowances_charges=allowances_charges,
            payment_means=payment_means,
            payment_terms=payment_terms_txt,
            due_date=due_date,
            line_items=line_items,
            preceding_invoice_reference=preceding_ref,
            preceding_invoice_date=preceding_date,
        )

    def _parse_party_cii(self, el: Optional[etree._Element]) -> EN16931Party:
        if el is None:
            return EN16931Party(
                name="",
                address=EN16931Address(line_one="", city="", postcode="", country_code="XX"),
            )

        def txt(path: str) -> Optional[str]:
            results = el.xpath(path + "/text()", namespaces={"ram": _RAM, "udt": _UDT})
            return str(results[0]).strip() if results else None

        name = txt("ram:Name")
        vat_id = txt("ram:SpecifiedTaxRegistration/ram:ID")

        ep_el_list = el.xpath("ram:URIUniversalCommunication/ram:URIID",
                              namespaces={"ram": _RAM})
        endpoint = None
        scheme = None
        if ep_el_list:
            ep_el = ep_el_list[0]
            endpoint = ep_el.text.strip() if ep_el.text else None
            scheme = ep_el.get("schemeID")

        addr_el_list = el.xpath("ram:PostalTradeAddress", namespaces={"ram": _RAM})
        addr_el = addr_el_list[0] if addr_el_list else None
        address = self._parse_address_cii(addr_el)

        contact_el_list = el.xpath("ram:DefinedTradeContact", namespaces={"ram": _RAM})
        contact_el = contact_el_list[0] if contact_el_list else None
        contact_name = contact_phone = contact_email = None
        if contact_el is not None:
            def ctxt(path: str) -> Optional[str]:
                r = contact_el.xpath(path + "/text()", namespaces={"ram": _RAM})
                return str(r[0]).strip() if r else None
            contact_name = ctxt("ram:PersonName")
            contact_phone = ctxt(
                "ram:TelephoneUniversalCommunication/ram:CompleteNumber"
            )
            contact_email = ctxt(
                "ram:EmailURIUniversalCommunication/ram:URIID"
            )

        return EN16931Party(
            name=name or "",
            address=address,
            vat_id=vat_id,
            electronic_address=endpoint,
            electronic_address_scheme=scheme,
            contact_name=contact_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
        )

    def _parse_address_cii(self, el: Optional[etree._Element]) -> EN16931Address:
        if el is None:
            return EN16931Address(line_one="", city="", postcode="", country_code="XX")

        def txt(local: str) -> Optional[str]:
            found = el.find(_q(_RAM, local))
            return found.text.strip() if found is not None and found.text else None

        return EN16931Address(
            line_one=txt("LineOne") or "",
            line_two=txt("LineTwo"),
            city=txt("CityName") or "",
            postcode=txt("PostcodeCode") or "",
            region=txt("CountrySubDivisionName"),
            country_code=txt("CountryID") or "XX",
        )

    def _parse_tax_cii(self, el: etree._Element) -> EN16931Tax:
        def txt(local: str) -> Optional[str]:
            found = el.find(_q(_RAM, local))
            return found.text.strip() if found is not None and found.text else None

        return EN16931Tax(
            category=txt("CategoryCode") or "S",
            rate=Decimal(txt("RateApplicablePercent") or "0"),
            taxable_amount=Decimal(txt("BasisAmount") or "0"),
            tax_amount=Decimal(txt("CalculatedAmount") or "0"),
            exemption_reason=txt("ExemptionReason"),
            exemption_reason_code=txt("ExemptionReasonCode"),
        )

    def _parse_payment_means_cii(self, el: etree._Element) -> EN16931PaymentMeans:
        def txt(local: str) -> Optional[str]:
            found = el.find(_q(_RAM, local))
            return found.text.strip() if found is not None and found.text else None

        type_code = txt("TypeCode") or "30"
        iban = bic = account_name = None
        acc_el = el.find(_q(_RAM, "PayeePartyCreditorFinancialAccount"))
        if acc_el is not None:
            iban_el = acc_el.find(_q(_RAM, "IBANID"))
            iban = iban_el.text.strip() if iban_el is not None and iban_el.text else None
            name_el = acc_el.find(_q(_RAM, "AccountName"))
            account_name = (
                name_el.text.strip() if name_el is not None and name_el.text else None
            )
        fi_el = el.find(_q(_RAM, "PayeeSpecifiedCreditorFinancialInstitution"))
        if fi_el is not None:
            bic_el = fi_el.find(_q(_RAM, "BICID"))
            bic = bic_el.text.strip() if bic_el is not None and bic_el.text else None

        return EN16931PaymentMeans(
            type_code=type_code,
            iban=iban,
            bic=bic,
            account_name=account_name,
        )

    def _parse_allowance_charge_cii(self, el: etree._Element) -> EN16931AllowanceCharge:
        def txt(local: str) -> Optional[str]:
            found = el.find(_q(_RAM, local))
            return found.text.strip() if found is not None and found.text else None

        is_charge_str = txt("ChargeIndicator") or "false"
        is_charge = is_charge_str.lower() == "true"
        amount = Decimal(txt("ActualAmount") or "0")
        base_el = el.find(_q(_RAM, "BasisAmount"))
        base_amount = Decimal(base_el.text or "0") if base_el is not None else None
        pct_el = el.find(_q(_RAM, "CalculationPercent"))
        percentage = Decimal(pct_el.text or "0") if pct_el is not None else None

        tc = el.find(_q(_RAM, "CategoryTradeTax"))
        tax_category = "S"
        tax_rate = Decimal("0")
        if tc is not None:
            cat = tc.find(_q(_RAM, "CategoryCode"))
            tax_category = cat.text.strip() if cat is not None and cat.text else "S"
            rate = tc.find(_q(_RAM, "RateApplicablePercent"))
            tax_rate = Decimal(rate.text or "0") if rate is not None else Decimal("0")

        return EN16931AllowanceCharge(
            is_charge=is_charge,
            amount=amount,
            base_amount=base_amount,
            percentage=percentage,
            reason=txt("Reason"),
            reason_code=txt("ReasonCode"),
            tax_category=tax_category,
            tax_rate=tax_rate,
        )

    def _parse_line_cii(self, el: etree._Element) -> EN16931LineItem:
        ns = {"ram": _RAM, "udt": _UDT}

        def txt(path: str) -> Optional[str]:
            r = el.xpath(path + "/text()", namespaces=ns)
            return str(r[0]).strip() if r else None

        line_id = txt("ram:AssociatedDocumentLineDocument/ram:LineID") or "1"
        name = txt("ram:SpecifiedTradeProduct/ram:Name") or ""
        description = txt("ram:SpecifiedTradeProduct/ram:Description")
        seller_id = txt("ram:SpecifiedTradeProduct/ram:SellerAssignedID")
        buyer_id = txt("ram:SpecifiedTradeProduct/ram:BuyerAssignedID")
        std_id = txt("ram:SpecifiedTradeProduct/ram:GlobalID")

        global_els = el.xpath("ram:SpecifiedTradeProduct/ram:GlobalID", namespaces=ns)
        std_scheme = global_els[0].get("schemeID") if global_els else None

        qty_els = el.xpath(
            "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", namespaces=ns
        )
        quantity = Decimal("1")
        unit_code = "C62"
        if qty_els:
            quantity = Decimal(qty_els[0].text or "1")
            unit_code = qty_els[0].get("unitCode", "C62")

        price_els = el.xpath(
            "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice"
            "/ram:ChargeAmount",
            namespaces=ns,
        )
        unit_price = Decimal(price_els[0].text or "0") if price_els else Decimal("0")

        bq_els = el.xpath(
            "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice"
            "/ram:BasisQuantity",
            namespaces=ns,
        )
        unit_price_base = Decimal(bq_els[0].text or "1") if bq_els else Decimal("1")

        total_els = el.xpath(
            "ram:SpecifiedLineTradeSettlement"
            "/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount",
            namespaces=ns,
        )
        line_net = Decimal(total_els[0].text or "0") if total_els else Decimal("0")

        acc_ref = txt(
            "ram:SpecifiedLineTradeSettlement"
            "/ram:ReceivableSpecifiedTradeAccountingAccount"
        )

        tax_cat_els = el.xpath(
            "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:CategoryCode",
            namespaces=ns,
        )
        tax_category = tax_cat_els[0].text.strip() if tax_cat_els and tax_cat_els[0].text else "S"

        tax_rate_els = el.xpath(
            "ram:SpecifiedLineTradeSettlement"
            "/ram:ApplicableTradeTax/ram:RateApplicablePercent",
            namespaces=ns,
        )
        tax_rate = (
            Decimal(tax_rate_els[0].text or "0") if tax_rate_els else Decimal("0")
        )

        line_ac_els = el.xpath(
            "ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeAllowanceCharge",
            namespaces=ns,
        )
        line_allowances = [self._parse_allowance_charge_cii(ac) for ac in line_ac_els]

        return EN16931LineItem(
            line_id=line_id,
            name=name,
            description=description,
            quantity=quantity,
            unit_code=unit_code,
            unit_price=unit_price,
            unit_price_base_quantity=unit_price_base,
            line_net_amount=line_net,
            tax_category=tax_category,
            tax_rate=tax_rate,
            buyer_accounting_reference=acc_ref,
            seller_article_id=seller_id,
            buyer_article_id=buyer_id,
            standard_article_id=std_id,
            standard_article_id_scheme=std_scheme,
            line_allowances=line_allowances,
        )
