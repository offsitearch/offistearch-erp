"""Template-based invoice PDF generator.

Draws invoice content on top of the studio's existing letterhead PDF
(``templates/pdf-template.pdf``), reusing its logo, header rule and
footer exactly as they are — no recreation, no quality loss.

Falls back to the legacy ``app.utils.pdf.invoice_pdf`` generator when
the template file is missing.
"""

from __future__ import annotations

import io
import logging
import re
import textwrap
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template path
# ---------------------------------------------------------------------------
_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"
_LETTERHEAD_PATH = _TEMPLATE_DIR / "pdf-template.pdf"

# ---------------------------------------------------------------------------
# Brand palette (sampled from the letterhead)
# ---------------------------------------------------------------------------
GOLD = (170 / 255, 131 / 255, 41 / 255)      # #AA8329
INK = (0.10, 0.10, 0.10)
GREY = (0.42, 0.42, 0.42)
PAGE_W, PAGE_H = letter                       # 612 x 792

# Safe content zone — learned from the template geometry
CONTENT_TOP = 674      # just under the header rule (rule sits at y≈700); leave breathing room below it
CONTENT_BOTTOM = 62    # stop above the footer band (band starts at y≈49)
LEFT_X = 37
RIGHT_X = 576

# Sign-off block geometry (dynamic, but kept clear of the footer).
SIGN_GAP = 40          # space between the body/totals and the "Thank you" line
BOX_PAD_TOP = 18       # space between the "Thank you" line and the box top
BOX_H = 78             # signature box height
BOX_PAD_BOTTOM = 16    # minimum clearance above the footer band

MISSING = "-----"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fallback(value: Any, fmt: str = "{}") -> str:
    """Return *fmt.format(value)* when *value* is truthy, else ``MISSING``."""
    if value is None or value == "" or value == 0:
        return MISSING
    return fmt.format(value)


_PDF_CURRENCY_PREFIX: dict[str, str] = {
    "INR": "Rs. ",
    "USD": "$",
    "EUR": "\u20ac",    # €
    "GBP": "\u00a3",    # £
    "JPY": "\u00a5",    # ¥
    "AED": "AED ",
    "SAR": "SAR ",
    "CAD": "C$",
    "AUD": "A$",
    "SGD": "S$",
}


def _fmt_currency(amount: Any, code: str = "INR") -> str:
    """Format *amount* with the given currency's symbol (core-font safe)."""
    if amount is None:
        return MISSING
    code = (code or "INR").upper()
    prefix = _PDF_CURRENCY_PREFIX.get(code, f"{code} ")
    amount = float(amount)
    negative = amount < 0
    amount = abs(amount)
    if code == "JPY":
        s = f"{amount:,.0f}"
    else:
        s = f"{amount:,.2f}"
    if negative:
        return f"-{prefix}{s}"
    return f"{prefix}{s}"


def _wrap(text: str, width: int = 68) -> list[str]:
    if not text:
        return [MISSING]
    lines = textwrap.wrap(text, width)
    return lines if lines else [MISSING]


# ---------------------------------------------------------------------------
# Core drawing
# ---------------------------------------------------------------------------

def _draw_invoice(c: canvas.Canvas, data: dict) -> None:
    """Render the full invoice onto *c* (may add pages)."""
    currency = (data.get("currency") or "INR").upper()
    y = CONTENT_TOP

    # -- "INVOICE" title, top right, gold --------------------------------
    c.setFillColorRGB(*GOLD)
    c.setFont("Times-Bold", 20)
    c.drawRightString(RIGHT_X, 733, "INVOICE")
    c.setFont("Times-Italic", 9)
    c.drawRightString(RIGHT_X, 721, _fallback(data.get("status")))

    # -- Two columns under the header rule, letter-style -----------------
    col_left_x = LEFT_X
    col_right_x = 340
    y_top = CONTENT_TOP

    # Left: Bill To
    bill_to = data.get("bill_to", {})
    c.setFont("Times-Bold", 11)
    c.setFillColorRGB(*INK)
    ty = y_top
    c.drawString(col_left_x, ty, _fallback(bill_to.get("name")))

    c.setFont("Times-Roman", 9.5)
    for line in bill_to.get("address_lines", []):
        ty -= 13
        c.drawString(col_left_x, ty, _fallback(line))

    contact_bits = [
        b for b in [bill_to.get("email"), bill_to.get("phone")] if b
    ]
    if contact_bits:
        ty -= 13
        c.drawString(col_left_x, ty, "  |  ".join(contact_bits))

    gstin = bill_to.get("gstin")
    if gstin:
        ty -= 13
        c.drawString(col_left_x, ty, f"GSTIN: {gstin}")

    project = data.get("project")
    if project:
        ty -= 16
        c.setFont("Times-Bold", 9.5)
        c.drawString(col_left_x, ty, "Project: ")
        w = c.stringWidth("Project: ", "Times-Bold", 9.5)
        c.setFont("Times-Roman", 9.5)
        c.drawString(col_left_x + w, ty, project)

    # Right: Reference / Issue / Due — right-aligned
    ry = y_top
    meta_rows = [
        ("Invoice No.:", data.get("reference_no", "")),
        ("Issue Date:", data.get("issue_date", "")),
        ("Due Date:", data.get("due_date", "")),
    ]
    for label, value in meta_rows:
        c.setFont("Times-Bold", 9.5)
        c.setFillColorRGB(*INK)
        c.drawString(col_right_x, ry, label)
        c.setFont("Times-Roman", 9.5)
        c.drawRightString(RIGHT_X, ry, _fallback(value))
        ry -= 15

    body_top = min(ty, ry) - 24

    # -- Items table ------------------------------------------------------
    col_desc_x = LEFT_X
    col_qty_x = 240
    col_hsn_x = 350
    col_rate_x = 478
    col_amt_x = RIGHT_X
    row_h = 20

    def _table_header(yy: float) -> float:
        c.setFillColorRGB(*GOLD)
        c.setStrokeColorRGB(*GOLD)
        c.rect(LEFT_X, yy - 16, RIGHT_X - LEFT_X, 20, fill=1, stroke=1)
        c.setFont("Times-Bold", 9)
        c.setFillColorRGB(1, 1, 1)
        c.drawString(col_desc_x + 6, yy - 10, "Description")
        c.drawCentredString(col_qty_x, yy - 10, "Qty")
        c.drawCentredString(col_hsn_x, yy - 10, "HSN/SAC")
        c.drawRightString(col_rate_x, yy - 10, "Rate")
        c.drawRightString(col_amt_x - 6, yy - 10, "Amount")
        return yy - 20

    y = _table_header(body_top)

    items = data.get("items", [])
    for item in items:
        if y < CONTENT_BOTTOM + 130:
            c.showPage()
            _draw_continuation_header(c)
            y = CONTENT_TOP
            y = _table_header(y)

        c.setStrokeColorRGB(0.75, 0.75, 0.75)
        c.setLineWidth(0.4)
        c.rect(LEFT_X, y - 16, RIGHT_X - LEFT_X, row_h, fill=0, stroke=1)

        c.setFont("Times-Roman", 9.5)
        c.setFillColorRGB(*INK)
        c.drawString(col_desc_x + 6, y - 10, _fallback(item.get("desc")))
        c.drawCentredString(col_qty_x, y - 10, _fallback(item.get("qty"), "{}"))
        c.drawCentredString(col_hsn_x, y - 10, _fallback(item.get("hsn")))
        c.drawRightString(col_rate_x, y - 10, _fmt_currency(item.get("rate"), currency))
        c.setFont("Times-Bold", 9.5)
        c.drawRightString(col_amt_x - 6, y - 10, _fmt_currency(item.get("amount"), currency))
        y -= row_h

    # -- Totals block (right-aligned) ------------------------------------
    subtotal = float(data.get("subtotal", 0))
    discount_pct = float(data.get("discount_pct", 0))
    gst_pct = float(data.get("gst_pct", 0))
    amount_paid = float(data.get("amount_paid", 0))

    discount_amt = subtotal * discount_pct / 100 if discount_pct else 0
    taxable = subtotal - discount_amt
    gst_amt = taxable * gst_pct / 100 if gst_pct else 0
    computed_total = taxable + gst_amt
    total = float(data.get("total", computed_total))
    balance_due = total - amount_paid

    ty2 = y - 18
    totals_rows: list[tuple[str, str, bool]] = [
        ("Subtotal", _fmt_currency(subtotal, currency), False),
    ]
    if discount_pct:
        totals_rows.append(
            (f"Discount ({discount_pct}%)", _fmt_currency(discount_amt, currency), False)
        )
    if gst_pct:
        totals_rows.append(
            (f"GST ({gst_pct}%)", _fmt_currency(gst_amt, currency), False)
        )
    if amount_paid:
        totals_rows.append(("Amount Paid", _fmt_currency(amount_paid, currency), False))
    totals_rows.append(("TOTAL DUE", _fmt_currency(balance_due, currency), True))

    for label, value, is_total in totals_rows:
        if is_total:
            c.setFillColorRGB(*GOLD)
            c.rect(340, ty2 - 20, RIGHT_X - 340, 24, fill=1, stroke=0)
            c.setFont("Times-Bold", 11)
            c.setFillColorRGB(1, 1, 1)
            c.drawString(348, ty2 - 12, label)
            c.drawRightString(RIGHT_X - 8, ty2 - 12, value)
            ty2 -= 24
        else:
            c.setFont("Times-Roman", 9.5)
            c.setFillColorRGB(*GREY)
            c.drawString(340, ty2 - 8, label)
            c.setFillColorRGB(*INK)
            c.drawRightString(RIGHT_X - 8, ty2 - 8, value)
            ty2 -= 16

    # -- Payment details + notes (left column) ---------------------------
    py = y - 18
    c.setFont("Times-Bold", 9.5)
    c.setFillColorRGB(*INK)
    c.drawString(LEFT_X, py, "Payment Details")
    py -= 14
    c.setFont("Times-Roman", 9)

    bd = data.get("bank_details", {})
    payment_lines = [
        f"A/c Name: {_fallback(bd.get('account_name'))}",
        f"Bank: {_fallback(bd.get('bank_name'))}    Branch: {_fallback(bd.get('branch'))}",
        f"A/c No.: {_fallback(bd.get('account_no'))}    IFSC: {_fallback(bd.get('ifsc'))}",
        f"UPI: {_fallback(bd.get('upi'))}",
    ]
    for line in payment_lines:
        c.drawString(LEFT_X, py, line)
        py -= 12

    notes = data.get("notes")
    if notes:
        py -= 8
        c.setFont("Times-Bold", 9.5)
        c.setFillColorRGB(*INK)
        c.drawString(LEFT_X, py, "Notes")
        py -= 12
        c.setFont("Times-Roman", 8.5)
        c.setFillColorRGB(*GREY)
        note_text = notes if isinstance(notes, str) else "\n".join(notes)
        for note_line in note_text.split("\n"):
            for wrapped in _wrap(note_line):
                c.drawString(LEFT_X, py, wrapped)
                py -= 11

    # -- Signature / acknowledgement block --------------------------------
    # Sign-off sits below the body with a clear gap from the totals and stays
    # dynamic (it follows the content). If it wouldn't fit above the footer on
    # the current page, it moves to its own continuation page — so it never
    # overlaps the data columns / total-pay box and never runs off-page.
    body_bottom = min(py, ty2)
    thank_you_y = body_bottom - SIGN_GAP
    box_top = thank_you_y - BOX_PAD_TOP
    box_bottom = box_top - BOX_H

    if box_bottom < CONTENT_BOTTOM + BOX_PAD_BOTTOM:
        c.showPage()
        _draw_continuation_header(c)
        thank_you_y = CONTENT_TOP - SIGN_GAP
        box_top = thank_you_y - BOX_PAD_TOP
        box_bottom = box_top - BOX_H

    mid_x = (LEFT_X + RIGHT_X) / 2
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.setLineWidth(0.6)
    c.rect(
        LEFT_X, box_bottom, RIGHT_X - LEFT_X, box_top - box_bottom,
        fill=0, stroke=1,
    )
    c.line(mid_x, box_bottom, mid_x, box_top)

    pad = 8
    # Left cell — client acknowledgement
    cy = box_top - 14
    c.setFont("Times-Bold", 9.5)
    c.setFillColorRGB(*INK)
    c.drawString(LEFT_X + pad, cy, _fallback(bill_to.get("name")))
    cy -= 14
    c.setFont("Times-Roman", 9)
    c.drawString(LEFT_X + pad, cy, "Signature:")
    cy -= 22
    c.drawString(LEFT_X + pad, cy, "Date:")

    # Right cell — Offsite authorisation
    cy = box_top - 14
    c.setFont("Times-Bold", 9.5)
    c.drawString(mid_x + pad, cy, "For Offsite,")
    cy -= 14
    c.setFont("Times-Roman", 9)
    c.drawString(mid_x + pad, cy, "Signature:")
    cy -= 22
    c.drawString(mid_x + pad, cy, f"Date: {_fallback(data.get('issue_date'))}")

    # Thank-you line
    c.setFont("Times-Italic", 9)
    c.setFillColorRGB(*GOLD)
    c.drawCentredString(
        PAGE_W / 2, thank_you_y,
        "Thank you for the opportunity to work on your project.",
    )


def _draw_continuation_header(c: canvas.Canvas) -> None:
    """Minimal header for 2nd+ pages of multi-page invoices."""
    c.setFillColorRGB(*INK)
    c.rect(LEFT_X, 700, RIGHT_X - LEFT_X, 0.7, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(*GOLD)
    c.drawRightString(RIGHT_X, 710, "INVOICE (continued)")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_invoice_pdf(data: dict) -> bytes:
    """Generate a branded invoice PDF.

    Draws invoice content on top of the studio letterhead template.
    Falls back to the legacy generator when the template is missing.

    Parameters
    ----------
    data : dict
        Invoice data with keys matching the ``invoice_pdf()`` interface:
        ``invoice_number``, ``client_name``, ``invoice_date``, ``due_date``,
        ``status``, ``items``, ``subtotal``, ``tax_percent``, ``tax_amount``,
        ``total``, ``paid_amount``, ``notes``, ``terms``, ``studio_info``,
        ``project_code``, ``project_name``, ``client_address``, ``client_gstin``,
        ``tax_lines``, ``payment_details``.
    """
    if not _LETTERHEAD_PATH.exists():
        logger.warning(
            "Invoice template not found at %s — falling back to legacy PDF generator",
            _LETTERHEAD_PATH,
        )
        from studioerp.pdf import invoice_pdf as legacy_invoice_pdf
        return legacy_invoice_pdf(**data)

    # Map the service-layer data dict to the drawing format
    bill_to_lines: list[str] = []
    if data.get("client_address"):
        bill_to_lines = [
            line.strip()
            for line in data["client_address"].split("\n")
            if line.strip()
        ]

    items = []
    for item in data.get("items", []):
        items.append({
            "desc": item.get("description", ""),
            "hsn": item.get("hsn_sac", ""),
            "qty": item.get("quantity", 1),
            "rate": item.get("rate", 0),
            "amount": item.get("amount", 0),
        })

    # GST percentage from tax_lines label or tax_percent field
    tax_pct = 0.0
    if data.get("tax_lines"):
        label = data["tax_lines"][0][0] if data["tax_lines"] else ""
        m = re.search(r"([\d.]+)%", label)
        if m:
            tax_pct = float(m.group(1))
    elif data.get("tax_percent"):
        tax_pct = float(data["tax_percent"])

    discount_pct = data.get("discount_pct", 0)

    # Payment details from studio_info
    pd = data.get("payment_details") or {}
    bank_details = {
        "account_name": pd.get("account_name", ""),
        "bank_name": pd.get("bank_name", ""),
        "account_no": pd.get("account_number", ""),
        "ifsc": pd.get("ifsc_code", ""),
        "branch": pd.get("branch", ""),
        "upi": pd.get("upi_id", ""),
    }

    draw_data = {
        "reference_no": data.get("invoice_number", ""),
        "issue_date": _format_date(data.get("invoice_date")),
        "due_date": _format_date(data.get("due_date")),
        "status": data.get("status", ""),
        "bill_to": {
            "name": data.get("client_name", ""),
            "address_lines": bill_to_lines,
            "email": "",
            "phone": "",
            "gstin": data.get("client_gstin", ""),
        },
        "project": _build_project_ref(data),
        "items": items,
        "discount_pct": discount_pct,
        "gst_pct": tax_pct,
        "subtotal": data.get("subtotal", 0),
        "total": data.get("total", 0),
        "amount_paid": float(data.get("paid_amount", 0)),
        "currency": (data.get("currency") or "INR").upper(),
        "bank_details": bank_details,
        "notes": data.get("notes") or data.get("terms") or "",
    }

    # 1. Draw invoice content into an in-memory overlay PDF
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _draw_invoice(c, draw_data)
    c.save()
    buf.seek(0)

    # 2. Merge overlay page(s) onto the letterhead template
    from pypdf import PdfReader, PdfWriter

    overlay_reader = PdfReader(buf)
    writer = PdfWriter()

    for i, _overlay_page in enumerate(overlay_reader.pages):
        base_page = PdfReader(str(_LETTERHEAD_PATH)).pages[0]
        base_page.merge_page(overlay_reader.pages[i])
        writer.add_page(base_page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _format_date(d: Any) -> str:
    """Format a date object to 'DD Mon YYYY' string, or ``MISSING``."""
    if d is None:
        return MISSING
    if hasattr(d, "strftime"):
        return d.strftime("%d %b %Y")
    return str(d)


def _build_project_ref(data: dict) -> str:
    """Build a project reference string.

    Intentionally prints only the project name: internal project codes are not
    shared with clients (we and the client may use different codes).
    """
    return data.get("project_name", "") or ""
