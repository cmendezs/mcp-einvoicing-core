"""QR code generation utilities for e-invoicing compliance.

Used by:
  ES — VERI*FACTU mandatory QR (HAC/1177/2024 Art. 10)
  ES — TicketBAI provincial QR (HuellaTBAI-based URL)
  FR — NF525 simplified-invoice QR

Requires the [qr] optional extra: pip install 'mcp-einvoicing-core[qr]'
"""

from __future__ import annotations

import base64
import io


def generate_qr_png_base64(
    content: str,
    *,
    size_px: int = 200,
    error_correction: str = "M",
) -> str:
    """Generate a QR code from a string and return it as a base64-encoded PNG.

    Args:
        content: The text or URL to encode in the QR.
        size_px: Approximate target image width/height in pixels. Exact output
            size depends on QR version and content length.
        error_correction: QR error correction level — L (7%), M (15%), Q (25%),
            or H (30%). Use M for most e-invoicing URLs. Use L only when space
            is very constrained.

    Returns:
        Base64-encoded PNG bytes string (no ``data:image/png;base64,`` prefix).

    Raises:
        ImportError: If ``qrcode[pil]`` is not installed.
        ValueError: If *error_correction* is not one of ``L``, ``M``, ``Q``,
            ``H``.
    """
    try:
        import qrcode  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "qrcode[pil] is required for QR generation. "
            "Install: pip install 'mcp-einvoicing-core[qr]'"
        ) from exc

    ec_levels = {
        "L": qrcode.ERROR_CORRECT_L,
        "M": qrcode.ERROR_CORRECT_M,
        "Q": qrcode.ERROR_CORRECT_Q,
        "H": qrcode.ERROR_CORRECT_H,
    }
    if error_correction not in ec_levels:
        raise ValueError(
            f"error_correction must be one of L, M, Q, H; got {error_correction!r}"
        )

    # box_size sets pixels per module; 33 is a conservative estimate for
    # the typical module count of a v2-v4 QR used in e-invoicing URLs.
    box_size = max(1, size_px // 33)
    qr = qrcode.QRCode(
        error_correction=ec_levels[error_correction],
        box_size=box_size,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    return base64.b64encode(buf.getvalue()).decode()
