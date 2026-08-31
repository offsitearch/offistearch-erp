"""Timesheet PDF generation pipeline: Jinja2 templating + Playwright Chromium.

Provides:
- ``group_entries_by_date()`` — pre-processes raw entries into date-grouped
  structure for the template.
- ``render_timesheet_html()`` — renders the Jinja2 HTML template.
- ``generate_timesheet_pdf()`` — launches Chromium via Playwright to render
  the content at US-Letter size, then merges the studio letterhead template
  (``pdf-template.pdf``) underneath every page.

This mirrors the invoice generator: the letterhead template supplies the
logo, header rule and footer so the timesheet shares the exact same branded
frame as invoices. Only the body content is generated per-report.
"""

import base64
import io
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "timesheet"

# Studio letterhead template shared with the invoice generator.
_LETTERHEAD_PATH = Path(__file__).resolve().parents[2] / "templates" / "pdf-template.pdf"

# Brand palette — sampled to match the invoice generator / letterhead.
GOLD = "#AA8329"

# US Letter page size (612 x 792). The margins below keep body content inside
# the template's safe zone (under the header rule at y~700, above the footer
# band at y~49), the same zone the invoice generator uses.
_LETTERHEAD_PATH_STR = str(_LETTERHEAD_PATH)

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

# ── Playwright browser singleton ────────────────────────────────────
_browser = None
_playwright = None


async def _get_browser():
    """Return the shared Chromium browser, launching on first call.

    If the previous browser was closed (e.g. event-loop restart during
    testing), both the Playwright instance and browser are recreated.
    """
    global _browser, _playwright
    if _browser is not None:
        try:
            if not _browser.is_connected():
                _browser = None
                _playwright = None
        except Exception:
            _browser = None
            _playwright = None
    if _browser is None:
        from playwright.async_api import async_playwright

        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch()
    return _browser


async def close_browser() -> None:
    """Shut down the shared browser (call on app shutdown)."""
    global _browser, _playwright
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None


# ── Data URI helper ─────────────────────────────────────────────────


def logo_to_data_uri(logo_path: str | Path | None) -> str | None:
    """Convert an image file to a base64 data URI for inline HTML use.

    Returns ``None`` if *logo_path* is ``None`` or the file cannot be read.
    """
    if logo_path is None:
        return None
    try:
        raw = Path(logo_path).read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        suffix = Path(logo_path).suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        return f"data:{mime};base64,{b64}"
    except Exception:
        logger.warning("Could not read logo file: %s", logo_path)
        return None


# ── Entry grouping ──────────────────────────────────────────────────


def group_entries_by_date(entries: list[dict]) -> list[dict]:
    """Group raw entry dicts by date for the HTML template.

    Each entry must have at least: ``date`` (str, "DD MMM" or ISO),
    ``hours``, ``project``, ``description``.  ``location`` is optional.

    Returns a list of groups::

        [{"date": "01 Aug", "color": "gray", "entries": [{...}, ...]}, ...]

    Consecutive date groups alternate between ``"gray"`` and ``"white"``
    so each day is visually distinct.
    """
    groups: list[dict] = []
    current_date = None
    current_group: dict | None = None
    color_cycle = ["gray", "white"]
    color_idx = 0

    for entry in entries:
        entry_date = entry["date"]
        if entry_date != current_date:
            if current_group is not None:
                color_idx += 1
            current_date = entry_date
            current_group = {
                "date": entry_date,
                "color": color_cycle[color_idx % 2],
                "entries": [],
            }
            groups.append(current_group)
        current_group["entries"].append(
            {
                "hours": entry.get("hours", ""),
                "project": entry.get("project", ""),
                "location": entry.get("location", ""),
                "description": entry.get("description", ""),
            }
        )

    return groups


# ── HTML rendering ──────────────────────────────────────────────────


def render_timesheet_html(context: dict) -> str:
    """Render the timesheet HTML template with the given context.

    Required keys: ``company_name``, ``company_tagline``, ``employee_name``,
    ``period_from``, ``period_to``, ``total_hours``, ``date_groups``.
    Optional: ``logo_path``, ``designation``, ``approved_by``.
    """
    template = _jinja_env.get_template("timesheet_template.html")
    return template.render(**context)


# ── PDF generation ──────────────────────────────────────────────────

# "TIMESHEET" title drawn in the letterhead's header band, top-right. It sits
# on the same baseline and right edge as the "INVOICE" title the invoice
# generator draws there, so it lines up with the studio logo. The invoice
# shows a status line ("Draft"/"Paid") right under the word; the timesheet has
# nothing to show there, so an invisible placeholder line reserves the same
# vertical space and keeps the title at the same level as the logo.
_HEADER_TEMPLATE = (
    "<div style='width:100%;height:100%;position:relative;'>"
    "<div style='position:absolute;right:45px;top:38px;color:" + GOLD + ";"
    "font-family:Times New Roman;font-size:20pt;font-weight:bold;'>"
    "TIMESHEET</div>"
    "<div style='position:absolute;right:45px;top:62px;color:transparent;"
    "font-family:Times New Roman;font-size:9pt;'>&nbsp;</div>"
    "</div>"
)


async def generate_timesheet_pdf(html_content: str) -> bytes:
    """Render HTML to a branded US-Letter PDF via Playwright Chromium.

    The body is rendered by Chromium within the template's safe content zone
    (under the header rule, above the footer band), then the letterhead
    template is merged underneath every page — so the logo, header rule and
    footer appear on all pages, exactly like invoices.

    Returns raw PDF bytes ready for an HTTP response.
    """
    if not _LETTERHEAD_PATH.exists():
        logger.warning(
            "Letterhead template not found at %s — emitting plain PDF "
            "(no branded frame)",
            _LETTERHEAD_PATH,
        )
        return await _render_plain(html_content)

    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.set_content(html_content, wait_until="networkidle")
        content_bytes = await page.pdf(
            format="Letter",
            print_background=True,
            display_header_footer=True,
            header_template=_HEADER_TEMPLATE,
            footer_template="<div></div>",
            margin={
                "top": "1.639in",      # content top at y=674, under header rule
                "bottom": "0.861in",   # content bottom at y=62, above footer
                "left": "0.514in",
                "right": "0.5in",
            },
        )
    finally:
        await page.close()

    return _merge_letterhead(content_bytes)


async def _render_plain(html_content: str) -> bytes:
    """Fallback when the letterhead template is missing: plain Letter PDF."""
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.set_content(html_content, wait_until="networkidle")
        return await page.pdf(
            format="Letter",
            print_background=True,
            margin={"top": "20mm", "bottom": "22mm", "left": "16mm", "right": "16mm"},
        )
    finally:
        await page.close()


def _merge_letterhead(content_bytes: bytes) -> bytes:
    """Merge the letterhead template beneath each rendered content page."""
    from pypdf import PdfReader, PdfWriter

    content_reader = PdfReader(io.BytesIO(content_bytes))
    writer = PdfWriter()

    for i in range(len(content_reader.pages)):
        base_page = PdfReader(_LETTERHEAD_PATH_STR).pages[0]
        base_page.merge_page(content_reader.pages[i])
        writer.add_page(base_page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
