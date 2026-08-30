"""Template-based salary slip (payslip) PDF generator.

Draws payslip content on top of the studio's existing letterhead PDF
(``templates/pdf-template.pdf``) — the same branded frame used by invoices
and timesheets — reusing its logo, header rule and footer exactly as they
are. The "SALARY SLIP" title sits in the header band level with the logo,
on the same right edge and baseline as the invoice generator's title, so
the whole document family lines up.

Falls back to the legacy ``app.utils.pdf.payslip_pdf`` generator when the
template file is missing.
"""

from __future__ import annotations

import io
import logging
import textwrap
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from studioerp.currency import format_amount

logger = logging.getLogger(__name__)

# Core-font-safe currency prefixes (₹ can't render in core fonts → "Rs. ").
_PDF_PREFIX: dict[str, str] = {
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

# ---------------------------------------------------------------------------
# Template path — same studio letterhead used for invoices/timesheets
# ---------------------------------------------------------------------------
_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"
_LETTERHEAD_PATH = _TEMPLATE_DIR / "pdf-template.pdf"

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
GOLD = (170 / 255, 131 / 255, 41 / 255)      # #AA8329
INK = (0.10, 0.10, 0.10)
GREY = (0.42, 0.42, 0.42)
LIGHT_BAND = (0.965, 0.965, 0.965)
PAGE_W, PAGE_H = letter                       # 612 x 792

# Safe content zone — under the header rule (y≈700), above the footer band
# (y≈49), matching the invoice generator.
CONTENT_TOP = 674
LEFT_X = 37
RIGHT_X = 576

MISSING = "-----"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fallback(value: Any, fmt: str = "{}") -> str:
    """Return *fmt.format(value)* when *value* is truthy, else ``MISSING``."""
    if value is None or value == "" or value == 0:
        return MISSING
    return fmt.format(value)


def _money(value: Any, currency: str = "INR") -> str:
    """Format an amount in the slip currency (core-font safe, Indian grouping for INR)."""
    if value is None:
        return MISSING
    code = (currency or "INR").upper()
    prefix = _PDF_PREFIX.get(code, f"{code} ")
    digits = format_amount(value, code=code, symbol=False)
    return f"{prefix}{digits}"


def wrap_text(text: str, width_chars: int) -> list[str]:
    return textwrap.wrap(text, width_chars) or [""]


def num_to_words_indian(n: int) -> str:
    """Integer rupees -> words, Indian numbering (lakh/crore)."""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
            "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
            "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
            "Eighty", "Ninety"]

    def two_digit(x):
        if x < 20:
            return ones[x]
        return (tens[x // 10] + (" " + ones[x % 10] if x % 10 else "")).strip()

    def three_digit(x):
        if x >= 100:
            return (ones[x // 100] + " Hundred" + (" " + two_digit(x % 100) if x % 100 else "")).strip()
        return two_digit(x)

    if n == 0:
        return "Zero"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1_000)
    hundred = n
    if crore:
        parts.append(three_digit(crore) + " Crore")
    if lakh:
        parts.append(three_digit(lakh) + " Lakh")
    if thousand:
        parts.append(three_digit(thousand) + " Thousand")
    if hundred:
        parts.append(three_digit(hundred))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _draw_slip(c: canvas.Canvas, data: dict) -> None:
    emp = data.get("employee") or {}
    att = data.get("attendance") or {}
    # Payslips are always denominated in INR (Indian employees, Indian payroll).
    currency = "INR"
    notes = data.get("notes") or []

    # -- "SALARY SLIP" title, top right, in the header band level with the
    #    logo (same right edge/baseline as the invoice title). -------------
    c.setFillColorRGB(*GOLD)
    c.setFont("Times-Bold", 20)
    c.drawRightString(RIGHT_X, 733, "SALARY SLIP")
    c.setFont("Times-Italic", 9)
    c.drawRightString(RIGHT_X, 721, f"Pay Period: {_fallback(data.get('pay_period'))}")

    # -- Two columns directly under the header rule -------------------------
    col_right_x = 340
    y_top = CONTENT_TOP

    # Left: employee details
    c.setFont("Times-Bold", 11)
    c.setFillColorRGB(*INK)
    ty = y_top
    c.drawString(LEFT_X, ty, _fallback(emp.get("name")))
    c.setFont("Times-Roman", 9.5)
    left_lines = [
        emp.get("designation"),
        f"Department: {emp.get('department')}",
        f"Employee ID: {emp.get('employee_id')}",
        f"Date of Joining: {emp.get('date_of_joining')}",
    ]
    for line in left_lines:
        ty -= 13
        c.drawString(LEFT_X, ty, _fallback(line))

    # Right: slip meta — inline "Label: value" pairs
    ry = y_top
    meta_rows = [
        ("Slip No.:", _fallback(data.get("slip_no"))),
        ("Pay Period:", _fallback(data.get("pay_period"))),
        ("Pay Date:", _fallback(data.get("pay_date"))),
        (
            "Paid Days:",
            f"{_fallback(att.get('paid_days'))} / {_fallback(att.get('total_days'))}",
        ),
    ]
    for label, value in meta_rows:
        c.setFont("Times-Bold", 9.5)
        c.setFillColorRGB(*INK)
        c.drawString(col_right_x, ry, label)
        c.setFont("Times-Roman", 9.5)
        c.drawRightString(RIGHT_X, ry, value)
        ry -= 15

    body_top = min(ty, ry) - 20

    # -- Bank strip ---------------------------------------------------------
    c.setFont("Times-Roman", 8.5)
    c.setFillColorRGB(*GREY)
    strip = "   |   ".join(
        part for part in (
            f"Bank: {_fallback(emp.get('bank_name'))}",
            f"A/c No.: {_fallback(emp.get('account_number'))}",
            f"IFSC: {_fallback(emp.get('ifsc_code'))}",
        ) if part
    )
    c.drawString(LEFT_X, body_top, strip)
    body_top -= 22

    # -- Earnings / Deductions, side-by-side tables -------------------------
    half_w = (RIGHT_X - LEFT_X - 16) / 2
    earn_x0 = LEFT_X
    earn_x1 = LEFT_X + half_w
    ded_x0 = earn_x1 + 16
    ded_x1 = RIGHT_X

    def side_header(x0, x1, yy, label):
        c.setFillColorRGB(*GOLD)
        c.rect(x0, yy - 16, x1 - x0, 20, fill=1, stroke=0)
        c.setFont("Times-Bold", 9)
        c.setFillColorRGB(1, 1, 1)
        c.drawString(x0 + 6, yy - 10, label)
        c.drawRightString(x1 - 6, yy - 10, "Amount")
        return yy - 20

    ey = side_header(earn_x0, earn_x1, body_top, "Earnings")
    dy = side_header(ded_x0, ded_x1, body_top, "Deductions")
    row_h = 18

    def side_rows(x0, x1, yy, rows):
        total = 0.0
        for i, (label, amt) in enumerate(rows):
            total += float(amt or 0)
            if i % 2 == 1:
                c.setFillColorRGB(*LIGHT_BAND)
                c.rect(x0, yy - 16, x1 - x0, row_h, fill=1, stroke=0)
            c.setFont("Times-Roman", 9)
            c.setFillColorRGB(*INK)
            c.drawString(x0 + 6, yy - 11, _fallback(str(label)))
            c.drawRightString(x1 - 6, yy - 11, _money(amt, currency))
            yy -= row_h
        return yy, total

    ey, gross = side_rows(earn_x0, earn_x1, ey, data.get("earnings") or [])
    dy, total_deductions = side_rows(ded_x0, ded_x1, dy, data.get("deductions") or [])

    # Level the two columns so both totals rows line up.
    row_diff = len(data.get("earnings") or []) - len(data.get("deductions") or [])
    if row_diff > 0:
        dy -= row_diff * row_h
    elif row_diff < 0:
        ey -= (-row_diff) * row_h

    # Totals row under each column
    bottom_y = min(ey, dy)
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.setLineWidth(0.6)
    c.line(earn_x0, bottom_y, earn_x1, bottom_y)
    c.line(ded_x0, bottom_y, ded_x1, bottom_y)
    c.setFont("Times-Bold", 9.5)
    c.setFillColorRGB(*INK)
    c.drawString(earn_x0 + 6, bottom_y - 13, "Gross Earnings")
    c.drawRightString(earn_x1 - 6, bottom_y - 13, _money(gross, currency))
    c.drawString(ded_x0 + 6, bottom_y - 13, "Total Deductions")
    c.drawRightString(ded_x1 - 6, bottom_y - 13, _money(total_deductions, currency))

    y = bottom_y - 34

    # -- Net Pay band (gold), full width — like the invoice's TOTAL DUE ----
    net_pay = gross - total_deductions
    c.setFillColorRGB(*GOLD)
    c.rect(LEFT_X, y - 22, RIGHT_X - LEFT_X, 26, fill=1, stroke=0)
    c.setFont("Times-Bold", 12)
    c.setFillColorRGB(1, 1, 1)
    c.drawString(LEFT_X + 10, y - 14, "NET PAY")
    c.drawRightString(RIGHT_X - 10, y - 14, _money(net_pay, currency))
    y -= 40

    c.setFont("Times-Italic", 8.5)
    c.setFillColorRGB(*GREY)
    c.drawString(LEFT_X, y, f"Net pay in words: Rupees {num_to_words_indian(int(net_pay))} Only")
    y -= 22

    # -- Notes --------------------------------------------------------------
    if notes:
        c.setFont("Times-Bold", 9.5)
        c.setFillColorRGB(*INK)
        c.drawString(LEFT_X, y, "Notes")
        y -= 13
        c.setFont("Times-Roman", 8.5)
        c.setFillColorRGB(*GREY)
        for note in notes:
            for wrapped in wrap_text(str(note), 95):
                c.drawString(LEFT_X, y, wrapped)
                y -= 11


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_payslip_pdf(data: dict) -> bytes:
    """Generate a branded salary-slip PDF and return raw bytes.

    Draws payslip content on top of the studio letterhead template. Falls
    back to the legacy ``pdf.payslip_pdf`` generator when the template is
    missing.

    Parameters
    ----------
    data : dict
        ``employee`` (name, designation, employee_id, department,
        ``date_of_joining``, ``bank_name``, ``account_number``, ``ifsc_code``),
        ``pay_period``, ``pay_date``, ``slip_no``, ``attendance``
        (``paid_days``, ``total_days``), ``earnings`` (list of
        ``(label, amount)``), ``deductions`` (list of ``(label, amount)``),
        ``notes`` (list of str). Amounts are always rendered in INR.
    """
    if not _LETTERHEAD_PATH.exists():
        logger.warning(
            "Payslip template not found at %s — falling back to legacy PDF generator",
            _LETTERHEAD_PATH,
        )
        from studioerp.pdf import payslip_pdf as legacy_payslip_pdf

        gross = sum(float(a or 0) for _, a in data.get("earnings") or [])
        deductions = sum(float(a or 0) for _, a in data.get("deductions") or [])
        emp = data.get("employee") or {}
        return legacy_payslip_pdf(
            employee_name=emp.get("name") or "",
            employee_id=emp.get("employee_id") or "",
            designation=emp.get("designation") or "",
            month_label=data.get("pay_period") or "",
            working_days=(data.get("attendance") or {}).get("paid_days") or 0,
            gross_salary=gross,
            deductions=deductions,
            net_pay=gross - deductions,
        )

    # 1. Draw slip content into an in-memory overlay PDF
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    _draw_slip(c, data)
    c.save()
    buf.seek(0)

    # 2. Merge the overlay page onto the letterhead template
    from pypdf import PdfReader, PdfWriter

    overlay_reader = PdfReader(buf)
    writer = PdfWriter()
    for overlay_page in overlay_reader.pages:
        base_page = PdfReader(str(_LETTERHEAD_PATH)).pages[0]
        base_page.merge_page(overlay_page)
        writer.add_page(base_page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
