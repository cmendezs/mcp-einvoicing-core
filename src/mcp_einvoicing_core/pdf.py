"""PDF/A-3 XML embedding utilities for mcp-einvoicing-core.

Provides PDFEmbedder, which attaches an XML invoice to a PDF file as a
named embedded file and updates the XMP metadata with the Factur-X extension
schema.  This is required for ZUGFeRD (Germany), Factur-X (France), and
any other format that delivers a hybrid PDF/XML invoice.

PDF/A-3 conformance requirements (ISO 19005-3):
  - The XML attachment is stored as an EmbeddedFile stream with /Type /EmbeddedFile.
  - The file specification includes /AFRelationship set to /Alternative (ZUGFeRD/Factur-X)
    or /Source (for reference copies).
    [Unverified: confirm correct AFRelationship for ZUGFeRD 2.3 vs XRechnung]
  - The document catalog's /AF array references the file specification.
  - The document catalog's /Names/EmbeddedFiles name tree also lists the file.
  - XMP metadata must include the Factur-X extension schema entry: both the
    pdfaExtension:schemas declaration (registering the fx: namespace as a
    PDF/A-3 extension schema) and the actual fx:* property values. Verified
    against a real Factur-X sample XMP supplied under
    mcp-einvoicing-de/specs/documentation/zugferd/2. FACTUR-X_extension_schema_example.xmp.txt
    (namespace URI, prefix, field names/descriptions, and the extension-schema
    block shape all confirmed 2026-08-21).

Requires pikepdf (optional dependency):
    pip install pikepdf
    # or
    pip install mcp-einvoicing-core[pdf]

Country package usage:

    from mcp_einvoicing_core.pdf import PDFEmbedder

    hybrid_pdf_bytes = PDFEmbedder.embed(
        pdf_bytes=plain_pdf_bytes,
        xml_bytes=zugferd_xml_bytes,
        filename="factur-x.xml",
        xmp_profile="EN 16931",
    )
"""

from __future__ import annotations

import io
import logging
import re

logger = logging.getLogger(__name__)

# Factur-X XMP extension schema namespace.
# Verified 2026-08-21 against mcp-einvoicing-de/specs/documentation/zugferd/
# 2. FACTUR-X_extension_schema_example.xmp.txt (a real Factur-X 1.09.2 sample
# XMP block); namespace URI and "fx" prefix both confirmed exactly as below.
_FX_NS = "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"

# PDF/A-3 conformance XMP metadata fields required for ZUGFeRD/Factur-X.
# Verified against the same sample: field names, order, and descriptions
# (DocumentFileName/DocumentType/Version/ConformanceLevel, all valueType
# "Text", category "external") match exactly.
_FX_FIELDS = ("ConformanceLevel", "DocumentFileName", "DocumentType", "Version")

# Static PDF/A extension-schema declaration block (pdfaExtension:schemas),
# registering the fx: namespace as a PDF/A-3 extension schema so a strict
# PDF/A-3 validator (e.g. veraPDF) accepts the non-standard fx:* properties
# written below. Previously missing from _inject_xmp_description: a real
# Factur-X sample XMP always carries both this declaration block AND the
# fx:* value block (see the source cited above). Content is fixed (no
# per-invoice variables), copied verbatim from the verified sample.
_FX_EXTENSION_SCHEMA_BLOCK = (
    '    <rdf:Description xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"\n'
    '        xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#"\n'
    '        xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#" rdf:about="">\n'
    "      <pdfaExtension:schemas>\n"
    "        <rdf:Bag>\n"
    '          <rdf:li rdf:parseType="Resource">\n'
    "            <pdfaSchema:schema>Factur-X PDFA Extension Schema</pdfaSchema:schema>\n"
    f"            <pdfaSchema:namespaceURI>{_FX_NS}</pdfaSchema:namespaceURI>\n"
    "            <pdfaSchema:prefix>fx</pdfaSchema:prefix>\n"
    "            <pdfaSchema:property>\n"
    "              <rdf:Seq>\n"
    '                <rdf:li rdf:parseType="Resource">\n'
    "                  <pdfaProperty:name>DocumentFileName</pdfaProperty:name>\n"
    "                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>\n"
    "                  <pdfaProperty:category>external</pdfaProperty:category>\n"
    "                  <pdfaProperty:description>The name of the embedded XML document</pdfaProperty:description>\n"
    "                </rdf:li>\n"
    '                <rdf:li rdf:parseType="Resource">\n'
    "                  <pdfaProperty:name>DocumentType</pdfaProperty:name>\n"
    "                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>\n"
    "                  <pdfaProperty:category>external</pdfaProperty:category>\n"
    "                  <pdfaProperty:description>The type of the hybrid document in capital letters, e.g. INVOICE or ORDER</pdfaProperty:description>\n"
    "                </rdf:li>\n"
    '                <rdf:li rdf:parseType="Resource">\n'
    "                  <pdfaProperty:name>Version</pdfaProperty:name>\n"
    "                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>\n"
    "                  <pdfaProperty:category>external</pdfaProperty:category>\n"
    "                  <pdfaProperty:description>The actual version of the standard applying to the embedded XML document</pdfaProperty:description>\n"
    "                </rdf:li>\n"
    '                <rdf:li rdf:parseType="Resource">\n'
    "                  <pdfaProperty:name>ConformanceLevel</pdfaProperty:name>\n"
    "                  <pdfaProperty:valueType>Text</pdfaProperty:valueType>\n"
    "                  <pdfaProperty:category>external</pdfaProperty:category>\n"
    "                  <pdfaProperty:description>The conformance level of the embedded XML document</pdfaProperty:description>\n"
    "                </rdf:li>\n"
    "              </rdf:Seq>\n"
    "            </pdfaSchema:property>\n"
    "          </rdf:li>\n"
    "        </rdf:Bag>\n"
    "      </pdfaExtension:schemas>\n"
    "    </rdf:Description>"
)

# Regexes used by identify() to read back the fx: rdf:Description block that
# embed() writes. Text-based (not lxml), matching _inject_xmp_description's
# existing approach, since the XMP xpacket wrapper is not reliably strict XML.
_FX_DESCRIPTION_RE = re.compile(r"<rdf:Description\b[^>]*>(.*?)</rdf:Description>", re.DOTALL)
_FX_FIELD_RE = re.compile(r"<fx:(\w+)>(.*?)</fx:\1>", re.DOTALL)
# Matches only the block that actually opens the fx: namespace (xmlns:fx=...),
# not the extension-schema declaration block above, which also mentions the
# same URI as plain text inside <pdfaSchema:namespaceURI>, so a naive substring
# match on _FX_NS would find that block first and wrongly report no fx: fields.
_FX_XMLNS_ATTR_RE = re.compile(r'xmlns:fx="' + re.escape(_FX_NS) + r'"')

# Canonical hybrid-PDF XML attachment filenames, in lookup order.
# The first two are confirmed against the "Filename" codelist in
# mcp-einvoicing-de/specs/documentation/zugferd/2_EN16931 code lists values
# v17b...xlsx (verified 2026-08-21): factur-x.xml and xrechnung.xml are the
# only two hybrid-invoice filenames in the current Factur-X 1.09.2 codelist
# ("order-x.xml" also exists there but is for Order-X, out of scope for an
# invoicing package). The trailing two are ZUGFeRD 1.x legacy filenames
# absorbed from DE's own fallback loop (_ZUGFERD_ATTACHMENT_FILENAMES),
# plausible for older real-world PDFs but NOT part of the current codelist,
# so they are tried only after the two spec-confirmed names.
CANONICAL_HYBRID_PDF_FILENAMES: tuple[str, ...] = (
    "factur-x.xml",
    "xrechnung.xml",
    "ZUGFeRD-invoice.xml",
    "zugferd-invoice.xml",
)


def _build_xmp_rdf_block(filename: str, profile: str) -> str:
    """Build the Factur-X rdf:Description block to inject into XMP metadata.

    Returns a string fragment (not a complete XMP document) that can be
    inserted into an existing XMP metadata stream.
    """
    return (
        f'    <rdf:Description rdf:about=""\n'
        f'        xmlns:fx="{_FX_NS}">\n'
        f"      <fx:ConformanceLevel>{profile}</fx:ConformanceLevel>\n"
        f"      <fx:DocumentFileName>{filename}</fx:DocumentFileName>\n"
        f"      <fx:DocumentType>INVOICE</fx:DocumentType>\n"
        f"      <fx:Version>1.0</fx:Version>\n"
        f"    </rdf:Description>"
    )


def _inject_xmp_description(existing_xmp: bytes, filename: str, profile: str) -> bytes:
    """Inject the Factur-X XMP blocks into existing XMP metadata.

    Inserts both the pdfaExtension:schemas declaration block (registering fx:
    as a PDF/A-3 extension schema) and the fx:* value block, immediately
    before the closing </rdf:RDF> tag. If no </rdf:RDF> tag is found, appends
    both blocks inside a minimal XMP wrapper.

    This is a text-based injection to avoid an xml.etree / lxml dependency loop.
    A full XMP-aware merge is left for a future pass.
    [Unverified: test the resulting XMP against a real PDF/A-3 validator
     (e.g. veraPDF) before relying on this for production conformance checks.
     The block shape is confirmed against a real sample, but this module has
     not itself been run through a validator.]
    """
    rdf_block = _build_xmp_rdf_block(filename, profile)
    combined = f"{_FX_EXTENSION_SCHEMA_BLOCK}\n{rdf_block}"
    try:
        xmp_str = existing_xmp.decode("utf-8", errors="replace")
    except Exception:
        xmp_str = ""

    close_tag = "</rdf:RDF>"
    if close_tag in xmp_str:
        # Insert our blocks just before the RDF closing tag
        xmp_str = xmp_str.replace(close_tag, f"{combined}\n  {close_tag}", 1)
        return xmp_str.encode("utf-8")

    # No existing RDF block — build a minimal XMP wrapper
    minimal = (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        f"{combined}\n"
        "  </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    )
    return minimal.encode("utf-8")


class PDFEmbedder:
    """Attach an XML document to a PDF as a PDF/A-3 named embedded file.

    All methods are static — no state is kept between calls.

    Requires pikepdf.  Import is deferred to the first call of embed() so
    that packages that do not use PDF functionality do not need pikepdf
    installed.
    """

    @staticmethod
    def embed(
        pdf_bytes: bytes,
        xml_bytes: bytes,
        *,
        filename: str = "factur-x.xml",
        afrelationship: str = "Alternative",
        xmp_profile: str | None = None,
    ) -> bytes:
        """Attach *xml_bytes* to *pdf_bytes* as a PDF/A-3 embedded file.

        Args:
            pdf_bytes:      Source PDF bytes.  Need not be PDF/A-3 conformant
                            beforehand; the output targets PDF/A-3b.
            xml_bytes:      XML document to attach (ZUGFeRD, Factur-X, …).
            filename:       Attachment filename.
                            Use "factur-x.xml" for ZUGFeRD/Factur-X, "xrechnung.xml"
                            for an XRechnung hybrid (confirmed against the "Filename"
                            codelist, see CANONICAL_HYBRID_PDF_FILENAMES).
            afrelationship: PDF/A-3 AFRelationship value (without leading slash).
                            "Alternative" is correct for ZUGFeRD and Factur-X.
                            [Unverified: confirm against ZUGFeRD 2.3 spec section 7.3]
            xmp_profile:    Factur-X ConformanceLevel string for XMP metadata
                            (e.g. "EN 16931", "MINIMUM", "EXTENDED").  When None,
                            XMP metadata is not modified.

        Returns:
            Modified PDF bytes with the XML attachment.

        Raises:
            ImportError: If pikepdf is not installed.
        """
        try:
            import pikepdf
            from pikepdf import Array, Dictionary, Name, String
        except ImportError as exc:
            raise ImportError(
                "pikepdf is required for PDF/A-3 embedding. "
                "Install it with: pip install pikepdf  "
                "(or: pip install 'mcp-einvoicing-core[pdf]')"
            ) from exc

        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            # ── 1. Embedded file stream ───────────────────────────────────────
            ef_stream = pdf.make_stream(xml_bytes)
            ef_stream["/Type"] = Name("/EmbeddedFile")
            ef_stream["/Subtype"] = Name("/application#2Fxml")
            ef_stream["/Params"] = Dictionary(Size=len(xml_bytes))

            # ── 2. File specification dictionary ─────────────────────────────
            file_spec = pdf.make_indirect(
                Dictionary(
                    Type=Name("/Filespec"),
                    F=String(filename),
                    UF=String(filename),
                    AFRelationship=Name(f"/{afrelationship}"),
                    Desc=String("Electronic invoice (ZUGFeRD / Factur-X)"),
                    EF=Dictionary(F=ef_stream, UF=ef_stream),
                )
            )

            # ── 3. Names / EmbeddedFiles name tree ────────────────────────────
            if "/Names" not in pdf.Root:
                pdf.Root["/Names"] = pdf.make_indirect(Dictionary())
            root_names = pdf.Root["/Names"]

            if "/EmbeddedFiles" not in root_names:
                root_names["/EmbeddedFiles"] = Dictionary(Names=Array())
            ef_names_tree = root_names["/EmbeddedFiles"]

            if "/Names" not in ef_names_tree:
                ef_names_tree["/Names"] = Array()
            ef_names_tree["/Names"].append(String(filename))
            ef_names_tree["/Names"].append(file_spec)

            # ── 4. /AF array in document catalog ──────────────────────────────
            if "/AF" not in pdf.Root:
                pdf.Root["/AF"] = Array()
            pdf.Root["/AF"].append(file_spec)

            # ── 5. XMP metadata ───────────────────────────────────────────────
            if xmp_profile is not None:
                existing_xmp: bytes = b""
                if "/Metadata" in pdf.Root:
                    try:
                        existing_xmp = bytes(pdf.Root["/Metadata"].read_bytes())
                    except Exception:
                        existing_xmp = b""

                new_xmp = _inject_xmp_description(existing_xmp, filename, xmp_profile)
                xmp_stream = pdf.make_stream(new_xmp)
                xmp_stream["/Type"] = Name("/Metadata")
                xmp_stream["/Subtype"] = Name("/XML")
                pdf.Root["/Metadata"] = xmp_stream

            # ── 6. Save ───────────────────────────────────────────────────────
            output = io.BytesIO()
            pdf.save(output)
            return output.getvalue()

    @staticmethod
    def extract(
        pdf_bytes: bytes, filename: str | None = "factur-x.xml"
    ) -> bytes | tuple[str, bytes] | None:
        """Extract a named XML attachment from a PDF/A-3 file.

        Args:
            pdf_bytes: PDF/A-3 file bytes.
            filename:  Attachment filename to look for. Defaults to
                       "factur-x.xml" for backward compatibility with earlier
                       versions of this method. Pass None to instead try each
                       of `CANONICAL_HYBRID_PDF_FILENAMES` in turn (absorbs
                       the filename-fallback loop country packages previously
                       had to implement themselves, see CORE-PDF-EXTRACT-1).

        Returns:
            When *filename* is a string: the raw bytes of the attachment, or
            None if not found (unchanged from earlier versions).
            When *filename* is None: a ``(matched_filename, xml_bytes)`` tuple
            for the first canonical name found, or None if none match.

        Raises:
            ImportError: If pikepdf is not installed.
        """
        if filename is None:
            for candidate in CANONICAL_HYBRID_PDF_FILENAMES:
                xml_bytes = PDFEmbedder._extract_named(pdf_bytes, candidate)
                if xml_bytes is not None:
                    return candidate, xml_bytes
            return None
        return PDFEmbedder._extract_named(pdf_bytes, filename)

    @staticmethod
    def _extract_named(pdf_bytes: bytes, filename: str) -> bytes | None:
        """Extract a single named XML attachment. Returns None if not found.

        Raises:
            ImportError: If pikepdf is not installed.
        """
        try:
            import pikepdf
        except ImportError as exc:
            raise ImportError(
                "pikepdf is required for PDF extraction. Install it with: pip install pikepdf"
            ) from exc

        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            root_names = pdf.Root.get("/Names")
            if root_names is None:
                return None
            ef_tree = root_names.get("/EmbeddedFiles")
            if ef_tree is None:
                return None
            names_array = ef_tree.get("/Names")
            if names_array is None:
                return None

            # The Names array alternates: [filename_string, filespec, ...]
            it = iter(names_array)
            for name_obj in it:
                spec_obj = next(it, None)
                if spec_obj is None:
                    break
                try:
                    if str(name_obj) == filename:
                        ef_dict = spec_obj.get("/EF") or spec_obj
                        stream = ef_dict.get("/F") or ef_dict.get("/UF")
                        if stream is not None:
                            return bytes(stream.read_bytes())
                except Exception:
                    continue
        return None

    @staticmethod
    def identify(pdf_bytes: bytes) -> dict[str, str | bool | None]:
        """Identify whether *pdf_bytes* is a Factur-X / ZUGFeRD hybrid PDF/A-3 file.

        Reads the XMP metadata block (if present) and extracts the Factur-X
        extension schema fields written by `embed()`
        (fx:ConformanceLevel, fx:DocumentType, fx:DocumentFileName, fx:Version).
        Does not fetch or validate the attachment itself, call `extract()`
        for that.

        The fx: namespace URI and field set are confirmed against a real
        Factur-X sample XMP (see the module docstring), not merely inferred.
        What remains unverified: a hybrid PDF produced by a *different* tool
        may use a different XMP schema, or may write only one of the two fx:
        blocks (`embed()` writes both the pdfaExtension:schemas declaration
        and the fx:* values, but third-party producers are not guaranteed
        to). This method then reports ``is_hybrid_pdf=False`` even though an
        XML attachment may still be present. Call `extract()` (with an
        explicit filename or ``filename=None`` for the canonical-name
        fallback) as a structural check independent of XMP.

        Returns a dict with keys ``is_hybrid_pdf``, ``conformance_level``,
        ``document_type``, ``document_filename``, ``version``. All string
        fields are None when no fx: XMP block is found.

        Raises:
            ImportError: If pikepdf is not installed.
        """
        try:
            import pikepdf
        except ImportError as exc:
            raise ImportError(
                "pikepdf is required for PDF identification. Install it with: pip install pikepdf"
            ) from exc

        result: dict[str, str | bool | None] = {
            "is_hybrid_pdf": False,
            "conformance_level": None,
            "document_type": None,
            "document_filename": None,
            "version": None,
        }

        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            if "/Metadata" not in pdf.Root:
                return result
            try:
                xmp_bytes = bytes(pdf.Root["/Metadata"].read_bytes())
            except Exception:
                return result

        xmp_str = xmp_bytes.decode("utf-8", errors="replace")
        if _FX_NS not in xmp_str:
            return result

        # A PDF may carry several <rdf:Description> blocks (dc:, xmp:,
        # pdfaExtension: schema declaration, fx: values, ...). Match on the
        # xmlns:fx="..." attribute specifically, not a bare substring check
        # for _FX_NS: the pdfaExtension:schemas declaration block also
        # mentions the same URI as plain text inside
        # <pdfaSchema:namespaceURI>, so a substring match can find that block
        # first and wrongly conclude there are no fx: fields.
        fx_block = None
        for candidate in _FX_DESCRIPTION_RE.finditer(xmp_str):
            if _FX_XMLNS_ATTR_RE.search(candidate.group(0)):
                fx_block = candidate
                break
        if fx_block is None:
            return result

        fields = dict(_FX_FIELD_RE.findall(fx_block.group(1)))
        if not fields:
            return result

        result["is_hybrid_pdf"] = True
        result["conformance_level"] = fields.get("ConformanceLevel")
        result["document_type"] = fields.get("DocumentType")
        result["document_filename"] = fields.get("DocumentFileName")
        result["version"] = fields.get("Version")
        return result
