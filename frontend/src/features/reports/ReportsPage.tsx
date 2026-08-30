import { useQuery } from '@tanstack/react-query';
import { Building2, Clock, Download, FileSpreadsheet, Loader2, Users } from 'lucide-react';
import { useState } from 'react';
import {
  downloadAttendanceFile,
  downloadReportFile,
  getAttendanceReport,
  getFinanceReport,
  getHrReport,
  getProjectsReport,
  getTimesheetsReport,
  getTimesheetEmployeeOptions,
} from '../../api/reports';
import { getDepartments } from '../../api/employees';
import { EmptyState } from '../../components/ui/EmptyState';
import { LogoLoader } from '../../components/LogoLoader';
import DatePicker from '../../components/ui/DatePicker';
import { useToast } from '../../components/Toast';
import {
  ATTENDANCE_STATUS_META,
  PROJECT_STATUS_OPTIONS,
  PROJECT_TYPE_OPTIONS,
  formatINR,
  levelLabel,
  projectStatusMeta,
  projectTypeLabel,
} from '../../lib/constants';
import { formatDate, formatDuration, formatMinutesDuration, formatTime, monthLabel, toISODate } from '../../lib/date';
import type { AttendanceReportRow, AttendanceStatus } from '../../lib/types';
import { inputClass, selectClass, secondaryBtnClass } from '../../lib/styles';
import { useTranslation } from 'react-i18next';

type TabKey = 'attendance' | 'projects' | 'finance' | 'hr' | 'timesheets';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'attendance', label: 'Attendance' },
  { key: 'projects', label: 'Projects' },
  { key: 'timesheets', label: 'Timesheets' },
  { key: 'finance', label: 'Finance' },
  { key: 'hr', label: 'HR' },
];

export default function ReportsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabKey>('attendance');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink sm:text-2xl">{t('reports.title')}</h1>
        <p className="mt-1 text-sm text-muted">
          {t('reports.attendanceProjectsFinanceHr')} — export to Google Sheets.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5 rounded-lg border border-border bg-surface p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition ${
              tab === t.key ? 'bg-orange text-white' : 'text-muted hover:text-ink'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'attendance' && <AttendanceReport />}
      {tab === 'projects' && <ProjectsReport />}
      {tab === 'timesheets' && <TimesheetsReport />}
      {tab === 'finance' && <FinanceReport />}
      {tab === 'hr' && <HrReport />}
    </div>
  );
}

function ReportHeader({
  title,
  subtitle,
  onExport,
}: {
  title: string;
  subtitle: string;
  onExport: () => void;
}) {
  const [exporting, setExporting] = useState(false);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-4 shadow-card">
      <div>
        <h2 className="text-base font-bold text-ink">{title}</h2>
        <p className="text-sm text-muted">{subtitle}</p>
      </div>
      <button
        onClick={() => {
          setExporting(true);
          onExport();
          setExporting(false);
        }}
        disabled={exporting}
        className={secondaryBtnClass}
      >
        {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
        Open in Sheets
      </button>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="mt-1 truncate text-xl font-bold tabular-nums text-ink" title={String(value)}>
        {value}
      </p>
    </div>
  );
}

/** Small side panel used for breakdowns (aging, expense categories, headcounts). */
function ReportPanel({
  title,
  columns,
  rows,
}: {
  title: string;
  columns: [string, string];
  rows: [string, string | number][];
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <p className="border-b border-border bg-surfaceWarm px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
      </p>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted">No data.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <tbody>
            {rows.map(([label, value], i) => (
              <tr key={i} className="border-b border-border last:border-0 hover:bg-surfaceWarm">
                <td className="px-4 py-2.5 text-ink">{label}</td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-ink">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {/* columns kept for a11y/labelling symmetry */}
      <span className="sr-only">{columns.join(', ')}</span>
    </div>
  );
}


function ReportTable({
  columns,
  rows,
  numericCols = [],
}: {
  columns: string[];
  rows: (string | number | null)[][];
  numericCols?: number[];
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-surfaceWarm text-xs uppercase tracking-wide text-muted">
              {columns.map((c, i) => (
                <th key={c} className={`px-4 py-3 font-semibold ${numericCols.includes(i) ? 'text-right' : ''}`}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-border last:border-0 hover:bg-surfaceWarm">
                {row.map((cell, j) => (
                  <td
                    key={j}
                    className={`whitespace-nowrap px-4 py-2.5 text-ink ${numericCols.includes(j) ? 'text-right tabular-nums' : ''}`}
                  >
                    {cell ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function todayISO(): string {
  return toISODate(new Date());
}

function monthStartISO(): string {
  const d = new Date();
  return toISODate(new Date(d.getFullYear(), d.getMonth(), 1));
}

function attendanceStatusLabel(status: string): string {
  return ATTENDANCE_STATUS_META[status as AttendanceStatus]?.label ?? status.replace(/_/g, ' ');
}

function AttendanceReport() {
  const { t } = useTranslation();
  const { toast } = useToast();
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayISO());

  const report = useQuery({
    queryKey: ['report-attendance', from, to],
    queryFn: () => getAttendanceReport(from, to, 'json'),
  });

  function handleExport() {
    downloadAttendanceFile(from, to, 'xlsx').then(
      () => toast('Attendance report downloaded — open in Google Sheets', 'success'),
      () => toast('Failed to export report', 'error'),
    );
  }

  return (
    <div className="space-y-4">
      <ReportHeader
        title="Attendance Report"
        subtitle={t('reports.attendanceReportSubtitle')}
        onExport={handleExport}
      />
      <div className="flex flex-wrap items-end gap-3">
        <label className="block text-xs font-medium text-muted">
          From
          <DatePicker value={from} onChange={setFrom} className="mt-1 w-40" />
        </label>
        <label className="block text-xs font-medium text-muted">
          To
          <DatePicker value={to} onChange={setTo} className="mt-1 w-40" />
        </label>
        <div className="ml-auto flex gap-2">
          <button
            onClick={() => {
              setFrom(monthStartISO());
              setTo(todayISO());
            }}
            className={secondaryBtnClass}
          >
            This month
          </button>
        </div>
      </div>
      {report.isPending ? (
        <LogoLoader />
      ) : (report.data ?? []).length === 0 ? (
        <EmptyState icon={FileSpreadsheet} title="No attendance records" text="Nothing logged in the selected range." />
      ) : (
        <ReportTable
          columns={['Date', 'Employee', 'Department', 'Status', 'Check-in', 'Check-out', 'Late', 'Hours']}
          numericCols={[6, 7]}
          rows={(report.data ?? []).map((r: AttendanceReportRow) => [
            formatDate(r.date),
            r.employee_id ? `${r.user_name} (${r.employee_id})` : r.user_name,
            r.department ?? '—',
            attendanceStatusLabel(r.status),
            r.check_in_time ? formatTime(r.check_in_time) : '—',
            r.check_out_time ? formatTime(r.check_out_time) : '—',
            r.late_minutes > 0 ? formatMinutesDuration(r.late_minutes) : '—',
            formatDuration(r.total_hours) || '—',
          ])}
        />
      )}
    </div>
  );
}

function ProjectsReport() {
  const { t } = useTranslation();
  const { toast } = useToast();
  const [status, setStatus] = useState('');
  const [projectType, setProjectType] = useState('');

  const report = useQuery({
    queryKey: ['report-projects', status, projectType],
    queryFn: () =>
      getProjectsReport({ status: status || undefined, project_type: projectType || undefined }),
  });

  function handleExport() {
    downloadReportFile(
      '/reports/projects',
      { status: status || undefined, project_type: projectType || undefined, format: 'xlsx' },
      'projects_report.xlsx',
    ).then(
      () => toast('Projects report downloaded — open in Google Sheets', 'success'),
      () => toast('Failed to export report', 'error'),
    );
  }

  const summary = report.data?.summary;

  return (
    <div className="space-y-4">
      <ReportHeader
        title="Projects Report"
        subtitle={t('reports.projectsReportSubtitle')}
        onExport={handleExport}
      />
      <div className="flex flex-wrap items-center gap-2">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={`${selectClass} w-48`}>
          <option value="">All statuses</option>
          {PROJECT_STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {projectStatusMeta(s).label}
            </option>
          ))}
        </select>
        <select
          value={projectType}
          onChange={(e) => setProjectType(e.target.value)}
          className={`${selectClass} w-44`}
        >
          <option value="">All types</option>
          {PROJECT_TYPE_OPTIONS.map((pt) => (
            <option key={pt} value={pt}>
              {projectTypeLabel(pt)}
            </option>
          ))}
        </select>
      </div>
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <SummaryCard label="Total projects" value={summary.total_projects} />
          <SummaryCard label="Active" value={summary.active_projects} />
          <SummaryCard label="Total budget" value={formatINR(summary.total_budget)} />
          <SummaryCard label="Studio fee" value={formatINR(summary.total_studio_fee)} />
          <SummaryCard label="Expenses" value={formatINR(summary.total_expenses)} />
          <SummaryCard label="Total hours" value={formatDuration(summary.total_hours) || '0m'} />
        </div>
      )}
      {report.isPending ? (
        <LogoLoader />
      ) : (report.data?.rows ?? []).length === 0 ? (
        <EmptyState icon={Building2} title="No projects match the filters" />
      ) : (
        <ReportTable
          columns={['Code', 'Name', 'Client', 'Type', 'Status', 'Progress', 'Budget', 'Fee', 'Expenses', 'Hours']}
          numericCols={[5, 6, 7, 8, 9]}
          rows={(report.data?.rows ?? []).map((r) => [
            r.project_code,
            r.name,
            r.client_name,
            projectTypeLabel(r.project_type as never),
            projectStatusMeta(r.status as never).label,
            `${r.progress_pct}%`,
            formatINR(r.budget),
            formatINR(r.studio_fee),
            formatINR(r.expenses),
            formatDuration(r.hours_logged) || '—',
          ])}
        />
      )}
    </div>
  );
}

const GROUP_BY_OPTIONS: { key: 'day' | 'week' | 'month'; label: string }[] = [
  { key: 'day', label: 'Daily' },
  { key: 'week', label: 'Weekly' },
  { key: 'month', label: 'Monthly' },
];

type EmployeeOption = {
  id: number;
  name: string;
  employee_id: string | null;
  department: string | null;
};

function PeopleMultiSelect({
  employees,
  selected,
  onToggle,
  onClear,
}: {
  employees: EmployeeOption[];
  selected: number[];
  onToggle: (id: number) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const q = query.trim().toLowerCase();
  const filtered = q
    ? employees.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          (e.employee_id ?? '').toLowerCase().includes(q),
      )
    : employees;

  const byDept = filtered.reduce<Record<string, EmployeeOption[]>>((acc, e) => {
    const key = e.department || 'Unassigned';
    (acc[key] = acc[key] || []).push(e);
    return acc;
  }, {});
  const deptNames = Object.keys(byDept).sort((a, b) => a.localeCompare(b));
  const selectedCount = selected.length;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          setQuery('');
        }}
        className={`${inputClass} mt-1 flex w-64 items-center justify-between gap-2 pr-2.5`}
      >
        <span className="truncate">
          {selectedCount === 0
            ? 'Select people…'
            : `${selectedCount} person${selectedCount === 1 ? '' : 's'} selected`}
        </span>
        <svg className="h-4 w-4 shrink-0 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute left-0 z-30 mt-1 w-80 rounded-lg border border-border bg-surface p-2 shadow-xl">
            <div className="relative mb-2">
              <svg
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
              </svg>
              <input
                type="text"
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search name or ID…"
                className="w-full rounded-md border border-border bg-surface py-1.5 pl-8 pr-2 text-sm text-ink outline-none focus:border-orange"
              />
            </div>
            <div className="max-h-64 overflow-y-auto">
              {deptNames.length === 0 ? (
                <p className="px-2 py-3 text-center text-xs text-muted">
                  {q ? 'No matches.' : 'No employees.'}
                </p>
              ) : (
                deptNames.map((dept) => (
                  <div key={dept} className="mb-1">
                    <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                      {dept}
                    </p>
                    {byDept[dept].map((e) => {
                      const checked = selected.includes(e.id);
                      return (
                        <label
                          key={e.id}
                          className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surfaceWarm"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => onToggle(e.id)}
                            className="accent-orange"
                          />
                          <span className="truncate text-ink">
                            {e.name}
                            {e.employee_id ? ` (${e.employee_id})` : ''}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
            {selectedCount > 0 && (
              <div className="mt-1 border-t border-border pt-2">
                <button type="button" onClick={onClear} className="w-full rounded-md px-2 py-1 text-center text-xs font-medium text-orange hover:bg-surfaceWarm">
                  Clear selection
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}


function TimesheetsReport() {
  const { toast } = useToast();
  const [from, setFrom] = useState(monthStartISO());
  const [to, setTo] = useState(todayISO());
  const [groupBy, setGroupBy] = useState<'day' | 'week' | 'month'>('day');
  const [departmentId, setDepartmentId] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([]);
  const [exporting, setExporting] = useState<string | null>(null);

  const filters = {
    from_date: from,
    to_date: to,
    group_by: groupBy,
    department_id: departmentId ? Number(departmentId) : undefined,
    employee_id: employeeId ? Number(employeeId) : undefined,
    user_ids: selectedUserIds.length ? selectedUserIds : undefined,
  };

  const report = useQuery({
    queryKey: ['report-timesheets', filters],
    queryFn: () => getTimesheetsReport(filters),
  });

  const departments = useQuery({
    queryKey: ['report-timesheets-departments'],
    queryFn: getDepartments,
  });

  const employees = useQuery({
    queryKey: ['report-timesheets-employees', filters.department_id ?? null],
    queryFn: () => getTimesheetEmployeeOptions(filters.department_id),
  });

  const allEmployees = useQuery({
    queryKey: ['report-timesheets-employees-all'],
    queryFn: () => getTimesheetEmployeeOptions(),
  });

  function handleExport(format: 'pdf' | 'xlsx') {
    setExporting(format);
    downloadReportFile(
      '/reports/timesheets',
      { ...filters, user_ids: selectedUserIds.length ? selectedUserIds.join(',') : undefined, format },
      `timesheets_report.${format}`,
    ).then(
      () => {
        setExporting(null);
        toast(format === 'xlsx' ? 'Timesheets report downloaded — open in Google Sheets' : `Timesheets report downloaded as ${format.toUpperCase()}`, 'success');
      },
      () => {
        setExporting(null);
        toast('Failed to export report', 'error');
      },
    );
  }

  const summary = report.data?.summary;
  const employeesData = report.data?.employees ?? [];

  function toggleUser(id: number) {
    setEmployeeId('');
    setSelectedUserIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-4 shadow-card">
        <div>
          <h2 className="text-base font-bold text-ink">Timesheets Report</h2>
          <p className="text-sm text-muted">Each employee's hours in one section — daily, weekly or monthly.</p>
        </div>
        <div className="flex items-center gap-2">
          {(['xlsx', 'pdf'] as const).map((format) => (
            <button
              key={format}
              onClick={() => handleExport(format)}
              disabled={exporting !== null}
              className={secondaryBtnClass}
            >
              {exporting === format ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : format === 'pdf' ? (
                <Download className="h-4 w-4" />
              ) : (
                <FileSpreadsheet className="h-4 w-4" />
              )}
              {format === 'xlsx' ? 'Open in Sheets' : format.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="block text-xs font-medium text-muted">
          From
          <DatePicker value={from} onChange={setFrom} className="mt-1 w-40" />
        </label>
        <label className="block text-xs font-medium text-muted">
          To
          <DatePicker value={to} onChange={setTo} className="mt-1 w-40" />
        </label>
        <label className="block text-xs font-medium text-muted">
          Department
          <select
            value={departmentId}
            onChange={(e) => {
              setDepartmentId(e.target.value);
              setEmployeeId('');
            }}
            className={`${selectClass} mt-1 w-48`}
          >
            <option value="">All departments</option>
            {(departments.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs font-medium text-muted">
          Employee
          <select
            value={employeeId}
            onChange={(e) => {
              setEmployeeId(e.target.value);
              setSelectedUserIds([]);
            }}
            className={`${selectClass} mt-1 w-52`}
          >
            <option value="">All employees</option>
            {(employees.data ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
                {e.employee_id ? ` (${e.employee_id})` : ''}
              </option>
            ))}
          </select>
        </label>
        <PeopleMultiSelect
          employees={allEmployees.data ?? []}
          selected={selectedUserIds}
          onToggle={toggleUser}
          onClear={() => setSelectedUserIds([])}
        />
        <div className="flex rounded-lg border border-border bg-surface p-0.5">
          {GROUP_BY_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => setGroupBy(opt.key)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                groupBy === opt.key ? 'bg-accent text-white' : 'text-muted hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="ml-auto">
          <button
            onClick={() => {
              setFrom(monthStartISO());
              setTo(todayISO());
            }}
            className={secondaryBtnClass}
          >
            This month
          </button>
        </div>
      </div>
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryCard label="Total hours" value={`${summary.total_hours}h`} />
          <SummaryCard label="Employees" value={summary.employees} />
          <SummaryCard label="Projects" value={summary.projects} />
          <SummaryCard
            label={groupBy === 'day' ? 'Days worked' : groupBy === 'week' ? 'Weeks' : 'Months'}
            value={summary.periods}
          />
        </div>
      )}
      {report.isPending ? (
        <LogoLoader />
      ) : employeesData.length === 0 ? (
        <EmptyState icon={Clock} title="No timesheet hours match these filters" />
      ) : (
        <div className="space-y-4">
          {employeesData.map((emp, idx) => (
            <section
              key={emp.user_id}
              className={`rounded-xl border border-border bg-surface p-4 shadow-card ${idx > 0 ? 'break-before-page print:mt-6' : ''}`}
            >
              <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-3">
                <div>
                  <h3 className="text-sm font-bold text-ink">{emp.employee_name}</h3>
                  <p className="text-xs text-muted">
                    {[emp.employee_id, emp.department, emp.approved_by_name ? `Approved by ${emp.approved_by_name}` : null].filter(Boolean).join(' · ') || '—'}
                  </p>
                </div>
                <p className="text-sm font-bold tabular-nums text-ink">{emp.total_hours}h total</p>
              </header>
              <div className="mt-3 space-y-4">
                {emp.groups.map((group) => (
                  <div key={group.label}>
                    <div className="flex items-baseline justify-between gap-2">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{group.label}</h4>
                      <span className="text-xs font-bold tabular-nums text-ink">{group.hours}h</span>
                    </div>
                    {group.rows.length === 0 ? (
                      <p className="mt-2 text-xs text-muted">No entries logged.</p>
                    ) : (
                      <table className="mt-1 w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border text-muted">
                            {groupBy === 'day' && <th className="py-1.5 pr-3 font-medium">Date</th>}
                            <th className="py-1.5 pr-3 font-medium">Project</th>
                            <th className="py-1.5 pr-3 font-medium">Description</th>
                            <th className="py-1.5 text-right font-medium">Hours</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.rows.map((row, rowIdx) => (
                            <tr key={rowIdx} className="border-b border-border/60 last:border-0">
                              {groupBy === 'day' && (
                                <td className="py-1.5 pr-3 whitespace-nowrap text-muted">
                                  {row.date ? formatDate(row.date) : '—'}
                                </td>
                              )}
                              <td className="py-1.5 pr-3 font-medium text-ink">{row.project}</td>
                              <td className="max-w-[28rem] truncate py-1.5 pr-3 text-muted" title={row.description ?? ''}>
                                {row.description || '—'}
                              </td>
                              <td className="py-1.5 text-right tabular-nums text-ink">{row.hours}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

const AGING_BUCKETS: { key: '0_30' | '31_60' | '61_90' | '90_plus'; label: string }[] = [
  { key: '0_30', label: 'Current (0–30 days)' },
  { key: '31_60', label: '31–60 days' },
  { key: '61_90', label: '61–90 days' },
  { key: '90_plus', label: '90+ days' },
];

function FinanceReport() {
  const { t } = useTranslation();
  const { toast } = useToast();
  const [period, setPeriod] = useState<'month' | 'quarter' | 'year' | 'all'>('month');

  const report = useQuery({
    queryKey: ['report-finance', period],
    queryFn: () => getFinanceReport({ period }),
  });

  function handleExport() {
    downloadReportFile('/reports/finance', { period, format: 'xlsx' }, 'finance_report.xlsx').then(
      () => toast('Finance report downloaded — open in Google Sheets', 'success'),
      () => toast('Failed to export report', 'error'),
    );
  }

  const summary = report.data?.summary;

  return (
    <div className="space-y-4">
      <ReportHeader
        title="Finance Report"
        subtitle={t('reports.financeReportSubtitle')}
        onExport={handleExport}
      />
      <div className="flex flex-wrap items-center gap-2">
        {(['month', 'quarter', 'year', 'all'] as const).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition ${
              period === p ? 'bg-orange text-white' : 'border border-border text-muted hover:text-ink'
            }`}
          >
            {p === 'all' ? 'All time' : p}
          </button>
        ))}
      </div>
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <SummaryCard label="Invoiced" value={formatINR(summary.invoiced)} />
          <SummaryCard label="Received" value={formatINR(summary.received)} />
          <SummaryCard label="Outstanding" value={formatINR(summary.outstanding)} />
          <SummaryCard label="Expenses" value={formatINR(summary.expenses)} />
          <SummaryCard label="Profit" value={formatINR(summary.profit)} />
          <SummaryCard label="Invoices" value={summary.invoice_count} />
        </div>
      )}
      {report.isPending ? (
        <LogoLoader />
      ) : (report.data?.rows ?? []).length === 0 ? (
        <EmptyState icon={FileSpreadsheet} title="No invoices in this period" />
      ) : (
        <>
          <ReportTable
            columns={['Invoice', 'Client', 'Date', 'Due', 'Total', 'Paid', 'Outstanding', 'Status']}
            numericCols={[4, 5, 6]}
            rows={(report.data?.rows ?? []).map((r) => [
              r.invoice_number,
              r.client_name,
              formatDate(String(r.invoice_date)),
              formatDate(String(r.due_date)),
              formatINR(r.total),
              formatINR(r.paid_amount),
              formatINR(r.outstanding),
              String(r.status).replace(/_/g, ' '),
            ])}
          />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ReportPanel
              title="Receivables aging (all time)"
              columns={['Bucket', 'Amount']}
              rows={AGING_BUCKETS.map(({ key, label }) => [label, formatINR(report.data?.aging?.[key])])}
            />
            <ReportPanel
              title="Approved expenses by category"
              columns={['Category', 'Amount']}
              rows={(report.data?.expense_rows ?? []).map((e) => [e.category.replace(/_/g, ' '), formatINR(e.amount)])}
            />
          </div>
        </>
      )}
    </div>
  );
}

function HrReport() {
  const { toast } = useToast();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const report = useQuery({
    queryKey: ['report-hr', month, year],
    queryFn: () => getHrReport({ month, year }),
  });

  function handleExport() {
    downloadReportFile('/reports/hr', { month, year, format: 'xlsx' }, 'hr_report.xlsx').then(
      () => toast('HR report downloaded — open in Google Sheets', 'success'),
      () => toast('Failed to export report', 'error'),
    );
  }

  const summary = report.data?.summary;

  return (
    <div className="space-y-4">
      <ReportHeader
        title="HR Report"
        subtitle={`Attendance summary for ${monthLabel(year, month - 1)}.`}
        onExport={handleExport}
      />
      <div className="flex flex-wrap items-center gap-2">
        <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className={`${selectClass} w-40`}>
          {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
            <option key={m} value={m}>
              {new Date(year, m - 1, 1).toLocaleDateString('en-IN', { month: 'long' })}
            </option>
          ))}
        </select>
        <select value={year} onChange={(e) => setYear(Number(e.target.value))} className={`${selectClass} w-28`}>
          {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>
      {summary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <SummaryCard label="Employees" value={summary.total_employees} />
          <SummaryCard label="Present days" value={summary.total_present_days} />
          <SummaryCard label="Absent days" value={summary.total_absent_days} />
          <SummaryCard
            label="Avg attendance"
            value={summary.avg_attendance_pct == null ? '—' : `${summary.avg_attendance_pct}%`}
          />
        </div>
      )}
      {report.isPending ? (
        <LogoLoader />
      ) : (report.data?.rows ?? []).length === 0 ? (
        <EmptyState icon={Users} title="No HR data for this month" />
      ) : (
        <>
          <ReportTable
            columns={['Employee ID', 'Name', 'Department', 'Designation', 'Level', 'Present', 'Absent', 'Attendance', 'Leave (YTD)']}
            numericCols={[5, 6, 7, 8]}
            rows={(report.data?.rows ?? []).map((r) => [
              r.employee_id,
              r.name,
              r.department,
              r.designation,
              r.org_level_code ? `${r.org_level_code} · ${levelLabel(String(r.org_level_code))}` : '—',
              r.present_days,
              r.absent_days,
              r.attendance_pct == null ? '—' : `${r.attendance_pct}%`,
              r.leave_days_ytd,
            ])}
          />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ReportPanel
              title="Headcount by department"
              columns={['Department', 'Employees']}
              rows={(report.data?.headcount_dept ?? []).map((d) => [d.department, d.count])}
            />
            <ReportPanel
              title="Headcount by level"
              columns={['Level', 'Employees']}
              rows={(report.data?.headcount_level ?? []).map((l) => [
                `${l.level} · ${levelLabel(l.level)}`,
                l.count,
              ])}
            />
          </div>
        </>
      )}
    </div>
  );
}
