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
  - XMP metadata must include the Factur-X extension schema entry.
    [Unverified: confirm XMP schema URI and required field set for ZUGFeRD 2.3]

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
from typing import Optional

logger = logging.getLogger(__name__)

# Factur-X XMP extension schema namespace
# [Unverified: confirm URI for ZUGFeRD 2.3; earlier versions may differ]
_FX_NS = "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"

# PDF/A-3 conformance XMP metadata fields required for ZUGFeRD/Factur-X
# [Unverified: confirm required fields and their values for ZUGFeRD 2.3]
_FX_FIELDS = ("ConformanceLevel", "DocumentFileName", "DocumentType", "Version")


def _build_xmp_rdf_block(filename: str, profile: str) -> str:
    """Build the Factur-X rdf:Description block to inject into XMP metadata.

    Returns a string fragment (not a complete XMP document) that can be
    inserted into an existing XMP metadata stream.
    """
    return (
        f'    <rdf:Description rdf:about=""\n'
        f'        xmlns:fx="{_FX_NS}">\n'
        f'      <fx:ConformanceLevel>{profile}</fx:ConformanceLevel>\n'
        f'      <fx:DocumentFileName>{filename}</fx:DocumentFileName>\n'
        f'      <fx:DocumentType>INVOICE</fx:DocumentType>\n'
        f'      <fx:Version>1.0</fx:Version>\n'
        f'    </rdf:Description>'
    )


def _inject_xmp_description(existing_xmp: bytes, filename: str, profile: str) -> bytes:
    """Inject the Factur-X rdf:Description block into existing XMP metadata.

    Inserts the block immediately before the closing </rdf:RDF> tag.
    If no </rdf:RDF> tag is found, appends the block inside a minimal XMP wrapper.

    This is a text-based injection to avoid an xml.etree / lxml dependency loop.
    A full XMP-aware merge is left for a future pass.
    [Unverified: test the resulting XMP against PDF/A validators before relying
     on this for production conformance checks.]
    """
    rdf_block = _build_xmp_rdf_block(filename, profile)
    try:
        xmp_str = existing_xmp.decode("utf-8", errors="replace")
    except Exception:
        xmp_str = ""

    close_tag = "</rdf:RDF>"
    if close_tag in xmp_str:
        # Insert our description just before the RDF closing tag
        xmp_str = xmp_str.replace(close_tag, f"{rdf_block}\n  {close_tag}", 1)
        return xmp_str.encode("utf-8")

    # No existing RDF block — build a minimal XMP wrapper
    minimal = (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        f"{rdf_block}\n"
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
        xmp_profile: Optional[str] = None,
    ) -> bytes:
        """Attach *xml_bytes* to *pdf_bytes* as a PDF/A-3 embedded file.

        Args:
            pdf_bytes:      Source PDF bytes.  Need not be PDF/A-3 conformant
                            beforehand; the output targets PDF/A-3b.
            xml_bytes:      XML document to attach (ZUGFeRD, Factur-X, …).
            filename:       Attachment filename.
                            Use "factur-x.xml" for ZUGFeRD/Factur-X.
                            [Unverified: confirm correct filename for XRechnung hybrid]
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
            file_spec = pdf.make_indirect(Dictionary(
                Type=Name("/Filespec"),
                F=String(filename),
                UF=String(filename),
                AFRelationship=Name(f"/{afrelationship}"),
                Desc=String("Electronic invoice (ZUGFeRD / Factur-X)"),
                EF=Dictionary(F=ef_stream, UF=ef_stream),
            ))

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
    def extract(pdf_bytes: bytes, filename: str = "factur-x.xml") -> bytes | None:
        """Extract a named XML attachment from a PDF/A-3 file.

        Returns the raw bytes of the attachment, or None if not found.

        Args:
            pdf_bytes: PDF/A-3 file bytes.
            filename:  Attachment filename to look for.

        Raises:
            ImportError: If pikepdf is not installed.
        """
        try:
            import pikepdf
        except ImportError as exc:
            raise ImportError(
                "pikepdf is required for PDF extraction. "
                "Install it with: pip install pikepdf"
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
