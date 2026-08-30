"""Ring 5 (comms) tests -- non-DB: pure logic in backup/audit/reports, and
route assembly of the six comms routers."""

import csv
import gzip
import io
import json
import types
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4


# Register the platform Department/OrgLevel mappers before importing ring 5
# models so any ORM metadata that resolves by-string relationship names does not
# trip configure_mappers(). Advisory only -- these tests never construct ORM
# instances (audit rows use SimpleNamespace).
import studioerp.platform.orgstructure.models as _org  # noqa: F401
import studioerp.platform.users as _users  # noqa: F401

from studioerp.rings.comms.backup.service import (
    _pack_payload,
    _serialize,
    decrypt_secret,
    encrypt_secret,
    make_state,
    verify_state,
)
from studioerp.rings.comms.audit.service import (
    _build_audit_csv,
    _build_audit_xlsx,
    _export_columns,
)
from studioerp.rings.comms.reports import service as rep


# --------------------------------------------------------------------------
# Ring 5 wiring: every comms router is mounted on the app
# --------------------------------------------------------------------------
class TestCommsRouting:
    def test_comms_routers_are_mounted(self):
        from studioerp.api.app import app

        paths = {getattr(r, "path", "") for r in app.routes}
        expected = {
            "/api/v1/dashboard/summary",
            "/api/v1/reports/projects",
            "/api/v1/reports/finance",
            "/api/v1/reports/timesheets",
            "/api/v1/reports/hr",
            "/api/v1/meetings",
            "/api/v1/notices",
            "/api/v1/audit-logs",
            "/api/v1/backup/status",
        }
        for p in expected:
            assert p in paths, f"missing route {p}"


# --------------------------------------------------------------------------
# backup: Fernet crypto + signed state + serialization/gzip (all pure)
# --------------------------------------------------------------------------
class TestBackupCrypto:
    def test_encrypt_decrypt_round_trip(self):
        secret = "1/abc123refresh-token"
        enc = encrypt_secret(secret)
        assert enc != secret
        assert decrypt_secret(enc) == secret

    def test_encrypt_none_passthrough(self):
        assert encrypt_secret(None) is None
        assert decrypt_secret(None) is None

    def test_decrypt_garbage_returns_none(self):
        assert decrypt_secret("not-a-valid-fernet-token") is None

    def test_round_trip_is_stable_within_key(self):
        assert decrypt_secret(encrypt_secret("x")) == "x"


class TestBackupState:
    def test_make_state_has_three_parts(self):
        assert len(make_state().split(".")) == 3

    def test_verify_fresh_state(self):
        assert verify_state(make_state()) is True

    def test_verify_none_or_empty(self):
        assert verify_state(None) is False
        assert verify_state("") is False

    def test_verify_malformed(self):
        assert verify_state("only-one") is False

    def test_verify_tampered_signature(self):
        state = make_state()
        nonce, ts, _ = state.split(".")
        bad_sig = "f" * 64
        assert verify_state(f"{nonce}.{ts}.{bad_sig}") is False

    def test_verify_expired_timestamp(self):
        nonce = "n"
        import time
        old_ts = int(time.time()) - 3600
        import hashlib
        import hmac
        from studioerp.config import settings
        msg = f"{nonce}.{old_ts}".encode()
        sig = hmac.new(settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()
        assert verify_state(f"{nonce}.{old_ts}.{sig}") is False


class TestBackupSerialize:
    def test_datetime_before_date(self):
        dt = datetime(2026, 8, 30, 12, 30, 0)
        assert _serialize(dt) == "2026-08-30T12:30:00"

    def test_date(self):
        assert _serialize(date(2026, 8, 30)) == "2026-08-30"

    def test_decimal(self):
        assert _serialize(Decimal("1234.50")) == "1234.50"

    def test_uuid(self):
        u = uuid4()
        assert _serialize(u) == str(u)

    def test_bytes(self):
        assert _serialize(b"\xde\xad") == "dead"

    def test_scalar_passthrough(self):
        assert _serialize(42) == 42


class TestBackupPack:
    def test_pack_payload_gzip_round_trip(self):
        payload = {"users": [{"id": 1, "name": "x"}], "empty": []}
        blob = _pack_payload(payload)
        assert blob[:2] == b"\x1f\x8b"
        decoded = json.loads(gzip.decompress(blob).decode("utf-8"))
        assert decoded == payload


# --------------------------------------------------------------------------
# audit: export builders (pure, SimpleNamespace logs)
# --------------------------------------------------------------------------
class TestAuditExport:
    def _log(self, **kw):
        base = {
            "id": 7,
            "action": "create",
            "entity_type": "project",
            "entity_id": 42,
            "ip_address": "127.0.0.1",
            "created_at": datetime(2026, 8, 30, 9, 0, 0),
        }
        base.update(kw)
        return types.SimpleNamespace(**base)

    def test_export_columns(self):
        assert _export_columns() == [
            "ID", "User", "Action", "Entity Type", "Entity ID", "IP Address", "Timestamp",
        ]

    def test_csv_contains_headers_and_row(self):
        rows = [(self._log(), "alice")]
        out = _build_audit_csv(rows, Counter({"create": 1}), Counter({"project": 1}))
        assert "Audit Log Export" in out
        assert "Action Breakdown" in out
        assert "create,1" in out
        assert "Entity Breakdown" in out
        assert "7,alice,create,project,42,127.0.0.1" in out
        # header row present
        assert "ID,User,Action,Entity Type,Entity ID,IP Address,Timestamp" in out

    def test_xlsx_is_valid_package(self):
        rows = [(self._log(), "alice")]
        blob = _build_audit_xlsx(rows, Counter({"create": 1}), Counter({}))
        assert blob[:4] == b"PK\x03\x04"


# --------------------------------------------------------------------------
# reports: formatting + period helpers + pure csv/xlsx builders
# --------------------------------------------------------------------------
class TestReportsFormatting:
    def test_fmt_money_none(self):
        assert rep._fmt_money(None) == "\u20b90.00"

    def test_fmt_money(self):
        assert rep._fmt_money(1000000) == "\u20b91,000,000.00"

    def test_fmt_int_none_and_value(self):
        assert rep._fmt_int(None) == "0"
        assert rep._fmt_int(1234) == "1,234"

    def test_fmt_pct(self):
        assert rep._fmt_pct(None) == "N/A"
        assert rep._fmt_pct(12.5) == "12.5%"

    def test_month_end_december(self):
        assert rep._month_end(2026, 12) == date(2026, 12, 31)

    def test_month_end_february(self):
        # 2026 is not a leap year
        assert rep._month_end(2026, 2) == date(2026, 2, 28)

    def test_period_key_month(self):
        assert rep._period_key(date(2026, 8, 17), "month") == date(2026, 8, 1)

    def test_period_key_week_monday(self):
        # 17 Aug 2026 is a Monday; 19 Aug is Wednesday but groups back to Monday
        assert rep._period_key(date(2026, 8, 19), "week") == date(2026, 8, 17)

    def test_period_label_month(self):
        assert rep._period_label(date(2026, 8, 1), "month") == "August 2026"


class TestReportsCsvBuilders:
    def test_projects_csv(self):
        report = {
            "summary": {
                "total_projects": 1,
                "active_projects": 1,
                "total_budget": 10000000,
                "total_studio_fee": 100000,
                "total_expenses": 20000,
                "total_hours": 120,
            },
            "rows": [
                {
                    "project_code": "P-001", "name": "Tower A",
                    "client_name": "Acme", "project_type": "residential",
                    "status": "design", "progress_pct": 50,
                    "budget": 10000000, "studio_fee": 100000,
                    "expenses": 20000, "hours_logged": 120,
                }
            ],
        }
        out = rep.projects_csv(report)
        assert "Project Code,Project Name,Client" in out
        assert "P-001" in out and "Tower A" in out

    def test_finance_csv(self):
        report = {
            "summary": {
                "period": "month",
                "from": "2026-08-01",
                "to": "2026-08-31",
                "invoiced": 50000,
                "received": 20000,
                "outstanding": 30000,
                "expenses": 0,
                "profit": 50000,
            },
            "aging": {"0_30": 30000, "31_60": 0, "61_90": 0, "90_plus": 0},
            "rows": [
                {
                    "invoice_number": "INV-1", "client_name": "Acme",
                    "invoice_date": date(2026, 8, 1), "due_date": date(2026, 8, 15),
                    "total": 50000, "paid_amount": 20000, "outstanding": 30000,
                    "status": "partial",
                }
            ],
        }
        out = rep.finance_csv(report)
        assert "Invoice #,Client" in out
        assert "INV-1" in out

    def test_hr_csv(self):
        report = {
            "summary": {
                "year": 2026,
                "month": 8,
                "total_employees": 1,
                "total_present_days": 20,
                "total_absent_days": 2,
                "avg_attendance_pct": 90.9,
            },
            "rows": [
                {
                    "employee_id": "E-1", "name": "Jane", "department": "Design",
                    "designation": "Architect", "org_level_code": "L4",
                    "present_days": 20, "absent_days": 2, "attendance_pct": 90.9,
                    "leave_days_ytd": 3.0,
                }
            ],
        }
        out = rep.hr_csv(report)
        assert "Employee ID,Name,Department" in out
        assert "E-1" in out and "Jane" in out

    def test_to_csv(self):
        out = rep._to_csv(["A", "B"], [[1, 2], [3, 4]])
        parsed = list(csv.reader(io.StringIO(out)))
        assert parsed[0] == ["A", "B"]
        assert parsed[1] == ["1", "2"]

    def test_to_xlsx_is_package(self):
        blob = rep._to_xlsx("T", {"k": "v"}, ["A"], [[1]])
        assert blob[:4] == b"PK\x03\x04"
