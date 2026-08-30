import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  addPayrollAdjustment,
  addPayrollEntries,
  approvePayrollEntry,
  cancelPayrollRun,
  createPayrollRun,
  deletePayrollRun,
  downloadPayslip,
  getPayroll,
  markPayrollRunPaid,
  processPayrollRun,
  removePayrollAdjustment,
  removePayrollEntry,
  reopenPayrollRun,
  submitPayrollReview,
  updatePayrollEntry,
} from '../../api/finance';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { LogoLoader } from '../../components/LogoLoader';
import { useToast } from '../../components/Toast';
import CurrencyInput from '../../components/ui/CurrencyInput';
import {
  formatINR,
  PAYMENT_METHOD_LABELS,
  PAYMENT_METHOD_OPTIONS,
  payrollEntryStatusMeta,
  payrollStatusMeta,
} from '../../lib/constants';
import { parseIndianCurrencyInput } from '../../lib/currencyInput';
import {
  inputClass,
  labelClass,
  primaryBtnClass,
  secondaryBtnClass,
  smallSelectClass,
} from '../../lib/styles';
import type { PayrollAdjustment, PayrollEntry, PayrollRun } from '../../lib/types';
import { useAuthStore } from '../../store/authStore';
import { FinanceTabs } from './components/FinanceTabs';

function errDetail(err: unknown): string | null {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? null;
}

function monthLabel(month: number, year: number): string {
  return new Date(year, month - 1, 1).toLocaleDateString('en-IN', {
    month: 'long',
    year: 'numeric',
  });
}

export default function PayrollPage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [key, setKey] = useState(() => {
    const now = new Date();
    return { month: now.getMonth() + 1, year: now.getFullYear() };
  });
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [newRunOpen, setNewRunOpen] = useState(false);

  const payroll = useQuery({
    queryKey: ['payroll', key.year, key.month],
    queryFn: () => getPayroll(key.month, key.year),
  });

  function shift(delta: number) {
    setSelectedRunId(null);
    setKey((prev) => {
      const total = prev.year * 12 + (prev.month - 1) + delta;
      return { year: Math.floor(total / 12), month: (total % 12) + 1 };
    });
  }

  const month = payroll.data;
  const runs = month?.runs ?? [];

  const totals = useMemo(() => {
    let net = 0;
    let headcount = 0;
    for (const run of runs) {
      net += Number(run.total_net);
      headcount += run.headcount;
    }
    return { net, headcount: runs.length > 0 ? headcount : month?.preview.length ?? 0 };
  }, [runs, month]);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['payroll', key.year, key.month] });
    queryClient.invalidateQueries({ queryKey: ['finance-overview'] });
  }

  const toastError = (err: unknown, fallback: string) => toast(errDetail(err) ?? fallback, 'error');

  const monthName = monthLabel(key.month, key.year);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t('finance.payroll')}</h1>
          <p className="mt-1 text-sm text-muted">{t('finance.payrollSubtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => shift(-1)} className="rounded-lg border border-border bg-surface p-2 text-muted transition hover:bg-surfaceWarm">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-semibold text-ink">
            {monthName}
          </span>
          <button onClick={() => shift(1)} className="rounded-lg border border-border bg-surface p-2 text-muted transition hover:bg-surfaceWarm">
            <ChevronRight className="h-4 w-4" />
          </button>
          <button onClick={() => setNewRunOpen(true)} className={primaryBtnClass}>
            <Plus className="h-4 w-4" /> New run
          </button>
        </div>
      </div>
      <FinanceTabs level={user?.org_level_code} />

      {payroll.isPending ? (
        <LogoLoader />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <SummaryCard label="Net payout this month" value={formatINR(totals.net)} />
            <SummaryCard label="Headcount" value={String(totals.headcount)} />
            <SummaryCard label="Payroll runs" value={String(runs.length)} />
          </div>

          {runs.length === 0 && (
            <div className="rounded-xl border border-border bg-surface px-5 py-12 text-center shadow-card">
              <p className="text-sm font-medium text-ink">No payroll runs for {monthName}.</p>
              <p className="mt-1 text-sm text-muted">
                {month?.preview.length
                  ? `${month.preview.length} employee${month.preview.length === 1 ? '' : 's'} are ready — create a run to build the month.`
                  : 'No salaried employees are available for this month.'}
              </p>
              <button onClick={() => setNewRunOpen(true)} className={`${primaryBtnClass} mt-4`}>
                <Plus className="h-4 w-4" /> Create first run
              </button>
            </div>
          )}

          <div className="space-y-4">
            {runs.map((run) => (
              <RunCard
                key={run.id}
                run={run}
                expanded={run.id === selectedRunId}
                onToggle={() => setSelectedRunId(run.id === selectedRunId ? null : run.id)}
                onInvalidate={invalidate}
                toastError={toastError}
              />
            ))}
          </div>
        </>
      )}

      {newRunOpen && (
        <NewRunModal
          month={key.month}
          year={key.year}
          onClose={() => setNewRunOpen(false)}
          onCreated={() => {
            setNewRunOpen(false);
            invalidate();
            toast('Run created', 'success');
          }}
          toastError={toastError}
        />
      )}
    </div>
  );
}

/* ── Run card ──────────────────────────────────────────────── */

function RunCard({
  run,
  expanded,
  onToggle,
  onInvalidate,
  toastError,
}: {
  run: PayrollRun;
  expanded: boolean;
  onToggle: () => void;
  onInvalidate: () => void;
  toastError: (err: unknown, fallback: string) => void;
}) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const meta = payrollStatusMeta(run.status);
  const entries = useMemo(
    () => [...run.entries].sort((a, b) => (a.user_name ?? '').localeCompare(b.user_name ?? '')),
    [run.entries],
  );
  const paidLabel = useMemo(() => {
    if (!run.paid_at) return null;
    return new Date(run.paid_at).toLocaleString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }, [run.paid_at]);

  const [addOpen, setAddOpen] = useState(false);
  const [editEntry, setEditEntry] = useState<PayrollEntry | null>(null);
  const [adjustEntry, setAdjustEntry] = useState<PayrollEntry | null>(null);
  const [paidOpen, setPaidOpen] = useState(false);
  const [confirm, setConfirm] = useState<{
    title: string;
    message: string;
    tone?: 'danger' | 'info';
    confirmLabel?: string;
    action: () => void;
  } | null>(null);

  function refetch() {
    onInvalidate();
  }

  const approve = useMutation({
    mutationFn: (userId: number) => approvePayrollEntry(run.id, userId),
    onSuccess: () => refetch(),
    onError: (err) => toastError(err, 'Could not approve entry'),
  });
  const removeEntry = useMutation({
    mutationFn: (userId: number) => removePayrollEntry(run.id, userId),
    onSuccess: () => refetch(),
    onError: (err) => toastError(err, 'Could not remove employee'),
  });
  const submit = useMutation({
    mutationFn: () => submitPayrollReview(run.id),
    onSuccess: (updated) => {
      refetch();
      toast(`Run #${updated.id} sent for review`, 'success');
    },
    onError: (err) => toastError(err, 'Could not submit for review'),
  });
  const reopen = useMutation({
    mutationFn: () => reopenPayrollRun(run.id),
    onSuccess: () => {
      refetch();
      toast('Run reopened to draft', 'success');
    },
    onError: (err) => toastError(err, 'Could not reopen run'),
  });
  const process = useMutation({
    mutationFn: () => processPayrollRun(run.id),
    onSuccess: (updated) => {
      refetch();
      toast(`Run #${updated.id} processed`, 'success');
    },
    onError: (err) => toastError(err, 'Could not process run'),
  });
  const cancel = useMutation({
    mutationFn: () => cancelPayrollRun(run.id),
    onSuccess: () => {
      refetch();
      toast('Run cancelled', 'success');
    },
    onError: (err) => toastError(err, 'Could not cancel run'),
  });
  const del = useMutation({
    mutationFn: () => deletePayrollRun(run.id),
    onSuccess: () => {
      refetch();
      toast('Run deleted', 'success');
    },
    onError: (err) => toastError(err, 'Could not delete run'),
  });

  const canEdit = run.status === 'draft';
  const inReview = run.status === 'review';
  const processed = run.status === 'processed';
  const paid = run.status === 'paid';
  const payRef = run.payment_reference
    ? ` · Ref: ${run.payment_reference}`
    : '';
  const readyToProcess = run.headcount > 0 && run.approved_count === run.headcount;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <button
        onClick={onToggle}
        className={`flex w-full flex-wrap items-center justify-between gap-3 px-5 py-4 text-left transition hover:bg-surfaceWarm ${
          expanded ? 'border-b border-border bg-surfaceWarm/60' : ''
        }`}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${meta.dot}`} aria-hidden="true" />
            <p className="truncate font-semibold text-ink">{run.title ? run.title : `Run #${run.id}`}</p>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${meta.badge}`}>{meta.label}</span>
          </div>
          <p className="mt-1 text-xs text-muted">
            {run.headcount} employee{run.headcount === 1 ? '' : 's'} · {run.approved_count}/{run.headcount} approved
            {run.payment_method ? ` · ${PAYMENT_METHOD_LABELS[run.payment_method as keyof typeof PAYMENT_METHOD_LABELS] ?? run.payment_method}` : ''}
            {payRef}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-bold text-ink">{formatINR(run.total_net)}</span>
          <span className="text-muted">▾</span>
        </div>
      </button>

      {expanded && (
        <div className="bg-surface">
          {(canEdit || inReview || processed) && (
            <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3">
              {canEdit && (
                <>
                  <button onClick={() => setAddOpen(true)} className={secondaryBtnClass}>
                    <Plus className="h-4 w-4" /> Add employees
                  </button>
                  <button
                    onClick={() =>
                      setConfirm({
                        title: 'Submit for review',
                        message: `Send run #${run.id} for review? The run leaves draft; individual entries are approved from here.`,
                        confirmLabel: 'Submit for review',
                        tone: 'info',
                        action: () => submit.mutate(),
                      })
                    }
                    disabled={run.headcount === 0 || submit.isPending}
                    className={primaryBtnClass}
                  >
                    {submit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                    Submit for review
                  </button>
                  <button
                    onClick={() =>
                      setConfirm({
                        title: 'Delete run',
                        message: `Permanently delete run #${run.id} (${run.title || 'untitled'})? This cannot be undone.`,
                        confirmLabel: 'Delete run',
                        action: () => del.mutate(),
                      })
                    }
                    disabled={del.isPending}
                    className="inline-flex h-10 items-center gap-2 rounded-md border border-danger/30 bg-surface px-4 text-sm font-medium text-danger transition hover:bg-dangerSoft"
                  >
                    {del.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    Delete
                  </button>
                </>
              )}
              {inReview && (
                <>
                  <button onClick={() => reopen.mutate()} disabled={reopen.isPending} className={secondaryBtnClass}>
                    {reopen.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pencil className="h-4 w-4" />}
                    Reopen to draft
                  </button>
                  <button
                    onClick={() =>
                      setConfirm({
                        title: 'Process payroll',
                        message: `Process run #${run.id}? ${run.approved_count}/${run.headcount} entries are approved. Processing locks the numbers and generates payslips.`,
                        confirmLabel: 'Process payroll',
                        tone: 'info',
                        action: () => process.mutate(),
                      })
                    }
                    disabled={!readyToProcess || process.isPending}
                    className={primaryBtnClass}
                    title={!readyToProcess ? 'All entries must be approved first' : undefined}
                  >
                    {process.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                    Process payroll
                  </button>
                  <button
                    onClick={() =>
                      setConfirm({
                        title: 'Cancel run',
                        message: `Cancel run #${run.id}? It will be marked cancelled and can't be reopened.`,
                        confirmLabel: 'Cancel run',
                        action: () => cancel.mutate(),
                      })
                    }
                    disabled={cancel.isPending}
                    className="inline-flex h-10 items-center gap-2 rounded-md border border-danger/30 bg-surface px-4 text-sm font-medium text-danger transition hover:bg-dangerSoft"
                  >
                    {cancel.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    Cancel run
                  </button>
                </>
              )}
              {processed && (
                <>
                  <button onClick={() => reopen.mutate()} disabled={reopen.isPending} className={secondaryBtnClass}>
                    {reopen.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pencil className="h-4 w-4" />}
                    Reopen to draft
                  </button>
                  <button onClick={() => setPaidOpen(true)} className={primaryBtnClass}>
                    <Check className="h-4 w-4" /> Mark as paid
                  </button>
                </>
              )}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surfaceWarm text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-semibold">{t('employees.title')}</th>
                  <th className="px-3 py-3 font-semibold text-center">{t('finance.days')}</th>
                  <th className="px-3 py-3 font-semibold text-right">Basic</th>
                  <th className="px-3 py-3 font-semibold text-right">HRA</th>
                  <th className="px-3 py-3 font-semibold text-right">Special</th>
                  <th className="px-3 py-3 font-semibold text-right">Adjust.</th>
                  <th className="px-3 py-3 font-semibold text-right">PF</th>
                  <th className="px-3 py-3 font-semibold text-right">{t('finance.gross')}</th>
                  <th className="px-3 py-3 font-semibold text-right">{t('finance.deductions')}</th>
                  <th className="px-3 py-3 font-semibold text-right">{t('finance.netPay')}</th>
                  <th className="px-3 py-3 font-semibold text-center">Status / Actions</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <EntryRow
                    key={entry.user_id}
                    entry={entry}
                    run={run}
                    canEdit={canEdit}
                    inReview={inReview}
                    paidOrProcessed={paid || processed}
                    onEdit={() => setEditEntry(entry)}
                    onAdjust={() => setAdjustEntry(entry)}
                    onToggleApprove={() => approve.mutate(entry.user_id)}
                    onRemove={() =>
                      setConfirm({
                        title: 'Remove employee',
                        message: `Remove ${entry.user_name ?? 'this employee'} from run #${run.id}?`,
                        confirmLabel: 'Remove',
                        action: () => removeEntry.mutate(entry.user_id),
                      })
                    }
                  />
                ))}
              </tbody>
            </table>
            {entries.length === 0 && (
              <div className="px-5 py-10 text-center text-sm text-muted">
                No employees added yet.
                {canEdit && (
                  <button onClick={() => setAddOpen(true)} className={`${secondaryBtnClass} mx-auto mt-3`}>
                    <Plus className="h-4 w-4" /> Add employees
                  </button>
                )}
              </div>
            )}
          </div>

          {paid && paidLabel && (
            <div className="rounded-lg bg-successSoft px-4 py-3 text-sm text-success">
              Paid on {paidLabel}
              {run.payment_method
                ? ` via ${PAYMENT_METHOD_LABELS[run.payment_method as keyof typeof PAYMENT_METHOD_LABELS] ?? run.payment_method}`
                : ''}
              {run.payment_reference ? ` · Ref: ${run.payment_reference}` : ''}
            </div>
          )}
          {run.status === 'processed' && (
            <div className="rounded-lg bg-navy/10 px-4 py-3 text-sm text-navy">
              Run processed on {run.processed_at ? new Date(run.processed_at).toLocaleString() : '—'}. Payslips are frozen —
              download them from each row.
            </div>
          )}
          {run.status === 'cancelled' && (
            <div className="rounded-lg bg-dangerSoft px-4 py-3 text-sm text-danger">This run was cancelled.</div>
          )}
        </div>
      )}

      {addOpen && (
        <AddEmployeesModal run={run} onClose={() => setAddOpen(false)} onDone={refetch} toastError={toastError} />
      )}
      {editEntry && (
        <EntryEditModal
          entry={editEntry}
          run={run}
          onClose={() => setEditEntry(null)}
          onDone={refetch}
          toastError={toastError}
        />
      )}
      {adjustEntry && (
        <AdjustmentsModal
          entry={adjustEntry}
          run={run}
          onClose={() => setAdjustEntry(null)}
          onDone={refetch}
          toastError={toastError}
        />
      )}
      {paidOpen && <MarkPaidModal run={run} onClose={() => setPaidOpen(false)} onDone={refetch} toastError={toastError} />}
      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.confirmLabel}
          tone={confirm.tone}
          pending={false}
          onConfirm={() => {
            confirm.action();
            setConfirm(null);
          }}
          onClose={() => setConfirm(null)}
        />
      )}
    </div>
  );
}

/* ── Entry row ─────────────────────────────────────────────── */

function EntryRow({
  entry,
  run,
  canEdit,
  inReview,
  paidOrProcessed,
  onEdit,
  onAdjust,
  onToggleApprove,
  onRemove,
}: {
  entry: PayrollEntry;
  run: PayrollRun;
  canEdit: boolean;
  inReview: boolean;
  paidOrProcessed: boolean;
  onEdit: () => void;
  onAdjust: () => void;
  onToggleApprove: () => void;
  onRemove: () => void;
}) {
  const entryMeta = payrollEntryStatusMeta(entry.entry_status);
  const adjNet = Number(entry.additions_total ?? 0) - Number(entry.deductions_extra_total ?? 0);
  const hasAdjustments = entry.adjustments.length > 0;

  return (
    <tr className="border-b border-border last:border-0 hover:bg-surfaceWarm">
      <td className="px-5 py-3">
        <p className="font-semibold text-ink">
          {entry.user_name ?? 'Employee'}
          {entry.already_paid && (
            <span className="ml-2 rounded-full bg-warningSoft px-2 py-0.5 align-middle text-[10px] font-semibold text-warning">
              Already paid this month
            </span>
          )}
        </p>
        <p className="text-xs text-muted">
          {entry.employee_id ?? ''}
          {entry.department ? ` · ${entry.department}` : ''}
        </p>
      </td>
      <td className="px-3 py-3 text-center font-medium text-ink">
        {entry.working_days}
        <span className="text-muted">/{entry.total_days}</span>
      </td>
      <td className="px-3 py-3 text-right text-ink">{formatINR(entry.basic_amount)}</td>
      <td className="px-3 py-3 text-right text-ink">{formatINR(entry.hra_amount)}</td>
      <td className="px-3 py-3 text-right text-ink">{formatINR(entry.special_amount)}</td>
      <td
        className={`px-3 py-3 text-right ${adjNet > 0 ? 'text-success' : adjNet < 0 ? 'text-danger' : 'text-muted'}`}
      >
        {hasAdjustments ? `${adjNet > 0 ? '+' : '−'}${formatINR(Math.abs(adjNet))}` : '—'}
      </td>
      <td className="px-3 py-3 text-right text-danger">{formatINR(entry.pf_deduction)}</td>
      <td className="px-3 py-3 text-right text-ink">{formatINR(entry.gross_salary)}</td>
      <td className="px-3 py-3 text-right text-danger">{formatINR(entry.deductions)}</td>
      <td className="px-3 py-3 text-right font-bold text-ink">{formatINR(entry.net_pay)}</td>
      <td className="px-3 py-3">
        <div className="flex items-center justify-end gap-1.5">
          {!paidOrProcessed && (
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${entryMeta.badge}`}>
              {entryMeta.label}
            </span>
          )}
          {canEdit && (
            <>
              <button onClick={onEdit} title="Edit days / prorate / notes" className="rounded-lg p-1.5 text-muted transition hover:bg-surfaceWarm hover:text-ink">
                <Pencil className="h-4 w-4" />
              </button>
              <button onClick={onAdjust} title="Adjustments" className="rounded-lg p-1.5 text-muted transition hover:bg-surfaceWarm hover:text-ink">
                <Plus className="h-4 w-4" />
              </button>
              <button onClick={onRemove} title="Remove from run" className="rounded-lg p-1.5 text-muted transition hover:bg-dangerSoft hover:text-danger">
                <Trash2 className="h-4 w-4" />
              </button>
            </>
          )}
          {inReview && !paidOrProcessed && entry.entry_status !== 'approved' && (
            <button onClick={onToggleApprove} title="Approve entry" className="rounded-lg p-1.5 text-muted transition hover:bg-successSoft hover:text-success">
              <Check className="h-4 w-4" />
            </button>
          )}
          {paidOrProcessed && run.status !== 'cancelled' && <PayslipButton runId={run.id} userId={entry.user_id} />}
        </div>
      </td>
    </tr>
  );
}

function PayslipButton({ runId, userId }: { runId: number; userId: number }) {
  const { t } = useTranslation();
  const download = useMutation({
    mutationFn: () => downloadPayslip(runId, userId),
  });
  return (
    <button
      onClick={() => download.mutate()}
      disabled={download.isPending}
      title={t('finance.downloadPayslip')}
      className="rounded-lg p-1.5 text-muted transition hover:bg-surfaceWarm disabled:opacity-50"
    >
      {download.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
    </button>
  );
}

/* ── Base modal ────────────────────────────────────────────── */

function ModalShell({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navyDark/40 p-4 backdrop-blur-sm">
      <div
        className={`max-h-[90vh] w-full ${
          wide ? 'max-w-2xl' : 'max-w-md'
        } overflow-y-auto rounded-xl border border-border bg-surface shadow-overlay`}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h3 className="text-base font-bold text-ink">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-muted hover:bg-surfaceWarm">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

/* ── New run modal ─────────────────────────────────────────── */

function NewRunModal({
  month,
  year,
  onClose,
  onCreated,
  toastError,
}: {
  month: number;
  year: number;
  onClose: () => void;
  onCreated: () => void;
  toastError: (err: unknown, fallback: string) => void;
}) {
  const [title, setTitle] = useState('');
  const mutation = useMutation({
    mutationFn: () => createPayrollRun(month, year, title.trim()),
    onSuccess: onCreated,
    onError: (err) => toastError(err, 'Could not create run'),
  });
  return (
    <ModalShell title="New payroll run" onClose={onClose}>
      <p className="text-sm text-muted">
        Creating a run for <b className="text-ink">{monthLabel(month, year)}</b> starts it as an empty draft — you add
        employees next.
      </p>
      <label className={`${labelClass} mt-4`}>Run title (optional)</label>
      <input
        className={inputClass}
        value={title}
        maxLength={120}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="e.g. Final salary batch"
        autoFocus
      />
      <div className="mt-4 flex justify-end gap-2">
        <button onClick={onClose} className={secondaryBtnClass}>
          Cancel
        </button>
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className={primaryBtnClass}>
          {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Create run
        </button>
      </div>
    </ModalShell>
  );
}

/* ── Add employees modal ───────────────────────────────────── */

function AddEmployeesModal({
  run,
  onClose,
  onDone,
  toastError,
}: {
  run: PayrollRun;
  onClose: () => void;
  onDone: () => void;
  toastError: (err: unknown, fallback: string) => void;
}) {
  const month = useQuery({
    queryKey: ['payroll-prep', run.year, run.month],
    queryFn: () => getPayroll(run.month, run.year),
  });
  const existing = useMemo(() => new Set(run.entries.map((e) => e.user_id)), [run.entries]);
  const candidates = useMemo(
    () => (month.data?.preview ?? []).filter((e) => !existing.has(e.user_id)),
    [month.data, existing],
  );
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter((e) =>
      [e.user_name, e.employee_id, e.department, e.designation].some((v) =>
        v?.toLowerCase().includes(q),
      ),
    );
  }, [candidates, query]);
  const mutation = useMutation({
    mutationFn: (userIds: number[]) => addPayrollEntries(run.id, userIds),
    onSuccess: () => {
      onDone();
      onClose();
    },
    onError: (err) => toastError(err, 'Could not add employees'),
  });

  function toggle(userId: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  }

  return (
    <ModalShell title={`Add employees to run #${run.id}`} onClose={onClose} wide>
      {month.isPending ? (
        <LogoLoader />
      ) : (
        <>
          <input
            className={inputClass}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, employee ID, department or role"
            autoFocus
          />
          {candidates.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted">All salaried employees are already in this run.</p>
          ) : filtered.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted">No employees match your search.</p>
          ) : (
            <div className="mt-3 max-h-[50vh] overflow-y-auto rounded-lg border border-border">
              {filtered.map((e) => (
                <label
                  key={e.user_id}
                  className={`flex cursor-pointer items-center gap-3 border-b border-border px-4 py-3 last:border-0 hover:bg-surfaceWarm ${
                    selected.has(e.user_id) ? 'bg-navy/5' : ''
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(e.user_id)}
                    onChange={() => toggle(e.user_id)}
                    className="h-4 w-4 accent-orange"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-ink">
                      {e.user_name ?? 'Employee'}
                      {e.already_paid && (
                        <span className="ml-2 rounded-full bg-warningSoft px-1.5 py-0.5 align-middle text-[10px] font-semibold text-warning">
                          Already paid this month
                        </span>
                      )}
                    </span>
                    <span className="block text-xs text-muted">
                      {e.designation ?? '—'}
                      {e.department ? ` · ${e.department}` : ''} · {e.working_days} days · {formatINR(e.gross_salary)}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          )}
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-muted">
              {selected.size} selected / {filtered.length} shown
              {query.trim() && ` of ${candidates.length}`}
            </span>
            <div className="flex gap-2">
              <button onClick={onClose} className={secondaryBtnClass}>
                Cancel
              </button>
              <button
                onClick={() => mutation.mutate([...selected])}
                disabled={selected.size === 0 || mutation.isPending}
                className={primaryBtnClass}
              >
                {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add selected
              </button>
            </div>
          </div>
        </>
      )}
    </ModalShell>
  );
}

/* ── Edit entry modal ──────────────────────────────────────── */

function EntryEditModal({
  entry,
  run,
  onClose,
  onDone,
  toastError,
}: {
  entry: PayrollEntry;
  run: PayrollRun;
  onClose: () => void;
  onDone: () => void;
  toastError: (err: unknown, fallback: string) => void;
}) {
  const [workingDays, setWorkingDays] = useState(String(entry.working_days));
  const [prorate, setProrate] = useState(entry.prorate);
  const [notes, setNotes] = useState(entry.notes ?? '');
  const mutation = useMutation({
    mutationFn: () =>
      updatePayrollEntry(run.id, entry.user_id, {
        working_days: Math.max(0, Math.min(Number(workingDays) || 0, entry.total_days)),
        prorate,
        notes: notes.trim() || undefined,
      }),
    onSuccess: () => {
      onDone();
      onClose();
    },
    onError: (err) => toastError(err, 'Could not update entry'),
  });

  return (
    <ModalShell title={`Edit ${entry.user_name ?? 'employee'}`} onClose={onClose}>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Working days</label>
          <input
            className={inputClass}
            type="number"
            min={0}
            max={entry.total_days}
            value={workingDays}
            onChange={(e) => setWorkingDays(e.target.value)}
          />
          <p className="mt-1 text-xs text-muted">of {entry.total_days} payable days in the month</p>
        </div>
        <div className="flex items-end pb-2">
          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-ink">
            <input
              type="checkbox"
              checked={prorate}
              onChange={(e) => setProrate(e.target.checked)}
              className="h-4 w-4 accent-orange"
            />
            Prorate on working days
          </label>
        </div>
      </div>
      <label className={`${labelClass} mt-4`}>Notes</label>
      <textarea
        className={`${inputClass} h-20 w-full resize-none`}
        value={notes}
        maxLength={2000}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Optional notes for this employee's pay"
      />
      <div className="mt-4 flex justify-end gap-2">
        <button onClick={onClose} className={secondaryBtnClass}>
          Cancel
        </button>
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className={primaryBtnClass}>
          {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Save entry
        </button>
      </div>
    </ModalShell>
  );
}

/* ── Adjustments modal ─────────────────────────────────────── */

function AdjustmentsModal({
  entry,
  run,
  onClose,
  onDone,
  toastError,
}: {
  entry: PayrollEntry;
  run: PayrollRun;
  onClose: () => void;
  onDone: () => void;
  toastError: (err: unknown, fallback: string) => void;
}) {
  const [kind, setKind] = useState<'addition' | 'deduction'>('addition');
  const [category, setCategory] = useState('bonus');
  const [label, setLabel] = useState('');
  const [amount, setAmount] = useState('');
  const add = useMutation({
    mutationFn: () =>
      addPayrollAdjustment(run.id, entry.user_id, {
        kind,
        category,
        label: label.trim() || category,
        amount: parseIndianCurrencyInput(amount) ?? 0,
      }),
    onSuccess: () => {
      setLabel('');
      setAmount('');
      onDone();
    },
    onError: (err) => toastError(err, 'Could not add adjustment'),
  });
  const remove = useMutation({
    mutationFn: (adjustmentId: number) => removePayrollAdjustment(run.id, adjustmentId),
    onSuccess: () => onDone(),
    onError: (err) => toastError(err, 'Could not remove adjustment'),
  });

  return (
    <ModalShell title={`Adjustments for ${entry.user_name ?? 'employee'}`} onClose={onClose} wide>
      <div className="grid grid-cols-1 gap-2">
        {entry.adjustments.map((adj) => (
          <AdjustmentRow key={adj.id} adj={adj} onRemove={remove.mutate} pendingRemove={remove.isPending} />
        ))}
        {entry.adjustments.length === 0 && (
          <p className="py-3 text-center text-sm text-muted">No adjustments on this entry yet.</p>
        )}
      </div>

      <div className="mt-4 rounded-lg border border-border bg-surfaceWarm/50 p-4">
        <p className="mb-3 text-sm font-semibold text-ink">Add adjustment</p>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div>
            <label className={labelClass}>Type</label>
            <select
              className={smallSelectClass}
              value={kind}
              onChange={(e) => setKind(e.target.value as 'addition' | 'deduction')}
            >
              <option value="addition">Addition</option>
              <option value="deduction">Deduction</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>Category</label>
            <select className={smallSelectClass} value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="bonus">Bonus</option>
              <option value="incentive">Incentive</option>
              <option value="advance">Advance</option>
              <option value="penalty">Penalty</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>Label</label>
            <input
              className={inputClass}
              maxLength={120}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Festival bonus"
            />
          </div>
          <div>
            <label className={labelClass}>Amount</label>
            <CurrencyInput value={amount} onChange={setAmount} compact />
          </div>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            onClick={() => {
              const parsed = parseIndianCurrencyInput(amount);
              if (!parsed || parsed <= 0) {
                toastError(new Error('validation'), 'Enter a positive amount');
                return;
              }
              add.mutate();
            }}
            disabled={add.isPending || !label.trim() || !parsedAmount(amount)}
            className={primaryBtnClass}
          >
            {add.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add adjustment
          </button>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <button onClick={onClose} className={secondaryBtnClass}>
          Done
        </button>
      </div>
    </ModalShell>
  );
}

function parsedAmount(value: string): boolean {
  const n = parseIndianCurrencyInput(value);
  return !!n && n > 0;
}

function AdjustmentRow({
  adj,
  onRemove,
  pendingRemove,
}: {
  adj: PayrollAdjustment;
  onRemove: (id: number) => void;
  pendingRemove: boolean;
}) {
  const sign = adj.kind === 'addition' ? '+ ' : '− ';
  const color = adj.kind === 'addition' ? 'text-success' : 'text-danger';
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink">
          {adj.label} <span className="text-xs font-normal text-muted">· {adj.category}</span>
        </p>
        <p className={`text-xs font-semibold ${color}`}>
          {sign}
          {formatINR(adj.amount)}
        </p>
      </div>
      <button
        onClick={() => onRemove(adj.id)}
        disabled={pendingRemove}
        className="rounded-lg p-1.5 text-muted transition hover:bg-dangerSoft hover:text-danger"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

/* ── Mark as paid modal ────────────────────────────────────── */

function MarkPaidModal({
  run,
  onClose,
  onDone,
  toastError,
}: {
  run: PayrollRun;
  onClose: () => void;
  onDone: () => void;
  toastError: (err: unknown, fallback: string) => void;
}) {
  const [method, setMethod] = useState(run.payment_method ?? '');
  const [reference, setReference] = useState(run.payment_reference ?? '');
  const mutation = useMutation({
    mutationFn: () =>
      markPayrollRunPaid(run.id, {
        payment_method: method || undefined,
        payment_reference: reference.trim() || undefined,
      }),
    onSuccess: () => {
      onDone();
      onClose();
    },
    onError: (err) => toastError(err, 'Could not mark run as paid'),
  });
  return (
    <ModalShell title={`Mark run #${run.id} as paid`} onClose={onClose}>
      <p className="text-sm text-muted">
        Net payout: <b className="text-ink">{formatINR(run.total_net)}</b>
      </p>
      <div className="mt-4 grid grid-cols-1 gap-4">
        <div>
          <label className={labelClass}>Payment method (optional)</label>
          <select className={inputClass} value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="">—</option>
            {PAYMENT_METHOD_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {PAYMENT_METHOD_LABELS[m]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Payment reference (optional)</label>
          <input
            className={inputClass}
            maxLength={60}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="e.g. Bank UTR / cheque no."
          />
        </div>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button onClick={onClose} className={secondaryBtnClass}>
          Cancel
        </button>
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className={primaryBtnClass}>
          {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Mark as paid
        </button>
      </div>
    </ModalShell>
  );
}

/* ── Small shared pieces ───────────────────────────────────── */

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-ink">{value}</p>
    </div>
  );
}