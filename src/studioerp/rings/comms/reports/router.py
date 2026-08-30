"""Report generation routes (ring r5/comms).

Endpoints: /reports — projects, finance, timesheets, and HR reports with
JSON/CSV/XLSX/PDF export. The projects and finance reports contain financial
data and are executive-only (L0/L1) via ``require_financial_access`` — see
_ai_context/architecture/financial_access_policy.md. The HR and timesheets
reports carry no financial columns and remain L2.

Ported from ``app/modules/reports/routes.py``. PDF output uses the kernel's
pure-Python ``studioerp.pdf.timesheet_report_pdf``.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.db.session import get_db
from studioerp.pdf import timesheet_report_pdf
from studioerp.platform.deps import require_financial_access, require_min_level
from studioerp.platform.settings.service import get_studio_info
from studioerp.platform.users import User
from studioerp.rings.comms.reports import service as reports_service
from studioerp.time import now_local
from studioerp.xlsx import write_xlsx

router = APIRouter(prefix="/reports", tags=["reports"])

_FORMAT_PATTERN = "^(json|csv|xlsx)$"


def _export_response(
    title: str, summary: dict, columns: list[str], rows: list[list], format: str
) -> Response:
    if format == "csv":
        content = reports_service._to_csv(columns, rows)
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{title.replace(" ", "_").lower()}.csv"'
            },
        )
    content = reports_service._to_xlsx(title, summary, columns, rows)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{title.replace(" ", "_").lower()}.xlsx"'
        },
    )


@router.get("/projects")
async def projects_report(
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(default=None),
    project_type: str | None = Query(default=None),
    format: str = Query(default="json", pattern=_FORMAT_PATTERN),
):
    report = await reports_service.projects_report(db, status, project_type)
    if format == "xlsx":
        content = reports_service.projects_xlsx(report)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="projects_report.xlsx"'},
        )
    if format == "csv":
        content = reports_service.projects_csv(report)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="projects_report.csv"'},
        )
    return report


@router.get("/finance")
async def finance_report(
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(default="month", pattern="^(month|quarter|year|all)$"),
    format: str = Query(default="json", pattern=_FORMAT_PATTERN),
):
    report = await reports_service.finance_report(db, period)
    if format == "xlsx":
        content = reports_service.finance_xlsx(report)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="finance_report.xlsx"'},
        )
    if format == "csv":
        content = reports_service.finance_csv(report)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="finance_report.csv"'},
        )
    return report


@router.get("/timesheets/options")
async def timesheet_employee_options(
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: int | None = None,
):
    """Active employees for the timesheet report filters (L2+)."""
    return await reports_service.timesheet_employee_options(db, department_id)


@router.get("/timesheets")
async def timesheets_report(
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date = Query(default_factory=lambda: now_local().date() - timedelta(days=29)),
    to_date: date = Query(default_factory=lambda: now_local().date()),
    department_id: int | None = None,
    employee_id: int | None = None,
    user_ids: str | None = None,
    group_by: str = Query(default="day", pattern="^(day|week|month)$"),
    format: str = Query(default="json", pattern="^(json|csv|xlsx|pdf)$"),
):
    """Per-employee timesheet report (L2+).

    ``group_by`` picks the detail granularity — day lists every entry,
    week/month roll entries up per project within the period.
    ``department_id`` / ``employee_id`` narrow the scope. ``user_ids``
    is a comma-separated list of user ids (e.g. ``user_ids=1,4,7``) that
    selects multiple people across departments at once. ``format=pdf``
    renders one section per employee (each starting on a fresh page,
    flowing across pages when long); xlsx adds a Detail sheet; csv
    stays the flat project x employee aggregate.
    """
    parsed_user_ids: list[int] | None = None
    if user_ids:
        parsed_user_ids = [
            int(p.strip()) for p in user_ids.split(",") if p.strip().isdigit()
        ] or None
    if to_date < from_date:
        from_date, to_date = to_date, from_date
    report = await reports_service.timesheets_detail(
        db, from_date, to_date, department_id, employee_id, group_by, parsed_user_ids
    )
    columns = [
        "project_code",
        "project_name",
        "employee_id",
        "employee_name",
        "hours",
    ]
    rows = [[row[c] for c in columns] for row in report["rows"]]

    if format == "pdf":
        company = await get_studio_info(db)
        employees_pdf = []
        for emp in report["employees"]:
            groups_pdf = []
            for group in emp["groups"]:
                rows_pdf = []
                for r in group["rows"]:
                    rows_pdf.append(
                        {
                            "date": r.get("date") or "",
                            "project": r["project"],
                            "description": r.get("description") or "",
                            "hours": f"{r['hours']:g}",
                        }
                    )
                groups_pdf.append(
                    {
                        "label": group["label"],
                        "hours": f"{group['hours']:g}",
                        "rows": rows_pdf,
                    }
                )
            employees_pdf.append(
                {
                    "user_id": emp["user_id"],
                    "employee_name": emp["employee_name"],
                    "employee_id": emp["employee_id"],
                    "department": emp["department"],
                    "total_hours": f"{emp['total_hours']:g}",
                    "groups": groups_pdf,
                }
            )
        filters_line = (
            f"{company.get('name', 'Studio')}  |  Period: {from_date.strftime('%d %b %Y')} "
            f"to {to_date.strftime('%d %b %Y')}  |  "
            f"Generated: {now_local().date().strftime('%d %b %Y')}"
        )
        content = timesheet_report_pdf("Timesheet Report", filters_line, employees_pdf)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="timesheet_report_'
                    f"{from_date.isoformat()}_"
                    f'{to_date.isoformat()}.pdf"'
                )
            },
        )

    if format == "xlsx":
        today_str = now_local().date().isoformat()
        s = report["summary"]
        title = "Timesheets Report"

        # ── Summary sheet with KPIs ─────────────────────────────
        num_cols = 6
        kpi_items = [
            ("Date Range", f"{s['from']} to {s['to']}"),
            ("Total Hours", f"{s['total_hours']:,.1f}"),
            ("Employees", str(s["employees"])),
            ("Projects", str(s["projects"])),
            ("Periods", str(s["periods"])),
        ]
        extra_before: list[list[tuple[str, str | None]]] = [
            [(title, "title")] + [("", None)] * (num_cols - 1),
            [(f"Generated: {today_str}", "subtitle")] + [("", None)] * (num_cols - 1),
            [("", None)] * num_cols,
            [("Summary", "section")] + [("", None)] * (num_cols - 1),
        ]
        for label, value in kpi_items:
            extra_before.append([(label, "summary_label"), (str(value), "summary_value")] + [("", None)] * (num_cols - 2))

        # ── Aggregate detail rows ───────────────────────────────
        agg_columns = ["Project Code", "Project Name", "Employee ID", "Employee", "Hours"]
        agg_rows = [[row[c] for c in ["project_code", "project_name", "employee_id", "employee_name", "hours"]] for row in report["rows"]]
        total_hours_all = sum(r["hours"] for r in report["rows"])

        summary_sheet: dict = {
            "name": "Summary",
            "columns": agg_columns,
            "rows": agg_rows,
            "col_styles": ["text_border", "text_border", "text_border", "text_border", "decimal1_border"],
            "alt_col_styles": ["text_alt", "text_alt", "text_alt", "text_alt", "decimal1_alt"],
            "freeze_row": len(extra_before) + 1,
            "extra_rows_before": extra_before,
            "extra_rows_after": [
                [("TOTAL", "subtotal"), ("", None), ("", None), ("", None),
                 (f"{total_hours_all:g}" if isinstance(total_hours_all, float) else str(total_hours_all), "subtotal")],
            ],
        }

        # ── Detail sheet per employee ───────────────────────────
        detail_columns = ["Employee", "Period", "Date", "Project", "Description", "Hours"]
        detail_rows = []
        for emp in report["employees"]:
            for group in emp["groups"]:
                for r in group["rows"]:
                    detail_rows.append(
                        [
                            emp["employee_name"],
                            group["label"],
                            r.get("date") or "",
                            r["project"],
                            r.get("description") or "",
                            float(r["hours"]),
                        ]
                    )
        detail_sheet: dict = {
            "name": "Detail",
            "columns": detail_columns,
            "rows": detail_rows,
            "col_styles": ["text_border", "text_border", "text_border", "text_border", "text_border", "decimal1_border"],
            "alt_col_styles": ["text_alt", "text_alt", "text_alt", "text_alt", "text_alt", "decimal1_alt"],
            "freeze_row": 1,
        }

        content = write_xlsx([summary_sheet, detail_sheet])
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="timesheet_report.xlsx"'},
        )

    if format == "csv":
        return _export_response(report["title"], report["summary"], columns, rows, format)
    return report


@router.get("/hr")
async def hr_report(
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: int = Query(default_factory=lambda: now_local().date().month, ge=1, le=12),
    year: int = Query(default_factory=lambda: now_local().date().year, ge=2000, le=2100),
    format: str = Query(default="json", pattern=_FORMAT_PATTERN),
):
    report = await reports_service.hr_report(db, month, year)
    if format == "xlsx":
        content = reports_service.hr_xlsx(report)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="hr_report.xlsx"'},
        )
    if format == "csv":
        content = reports_service.hr_csv(report)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="hr_report.csv"'},
        )
    return report