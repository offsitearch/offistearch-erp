import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CalendarRange,
  FolderKanban,
  GanttChart,
  Layers,
  MapPin,
  Pencil,
  Plus,
  Trash2,
  UserRound,
  Users,
} from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getClients } from '../../api/clients';
import { getEmployees } from '../../api/employees';
import { getProjectFinance } from '../../api/finance';
import {
  addPhase,
  addTeamMember,
  deletePhase,
  deleteProject,
  getProject,
  getProjectTimeline,
  removeTeamMember,
  updatePhase,
  updateProject,
} from '../../api/projects';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { Skeleton } from '../../components/ui/Skeleton';
import {
  canAccess,
  formatCurrency,
  formatINR,
  phaseStatusMeta,
  projectTypeLabel,
} from '../../lib/constants';
import { useAuthStore } from '../../store/authStore';
import { useDecodedIdRequired as useDecodedId } from '../../lib/useDecodedId';
import { parseIndianCurrencyInput } from '../../lib/currencyInput';
import CurrencyInput from '../../components/ui/CurrencyInput';
import DatePicker from '../../components/ui/DatePicker';
import type { PhaseStatus, ProjectCreateInput, ProjectDetail } from '../../lib/types';
import { ProjectStatusBadge } from './components/ProjectStatusBadge';
import Breadcrumbs from '../../components/ui/Breadcrumbs';
import EditProjectModal from './components/EditProjectModal';
import PhaseEditModal from './components/PhaseEditModal';
import TimelineView from './components/TimelineView';
import { useTranslation } from 'react-i18next';

type Tab = 'overview' | 'phases' | 'team' | 'timeline';

const PHASE_FLOW: PhaseStatus[] = ['not_started', 'in_progress', 'completed'];

const PHASE_BAR_COLOR: Record<PhaseStatus, string> = {
  not_started: 'bg-graphite/30',
  in_progress: 'bg-info',
  completed: 'bg-success',
  delayed: 'bg-danger',
};

const secondaryBtnClass =
  'inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-surface px-3 text-sm font-medium text-ink transition hover:bg-surfaceWarm focus:outline-none focus-visible:ring-2 focus-visible:ring-navy/40';

export default function ProjectDetailPage() {
  const { t } = useTranslation();
  const projectId = useDecodedId();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const level = user?.org_level_code;

  // Financial data is executive-only (L0/L1) per the financial access policy.
  const canSeeMoney = canAccess(level, 'L1');

  const [tab, setTab] = useState<Tab>('overview');
  const [showAddMember, setShowAddMember] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [deletingProject, setDeletingProject] = useState(false);
  const [deletingPhaseId, setDeletingPhaseId] = useState<number | null>(null);

  const project = useQuery({ queryKey: ['project', projectId], queryFn: () => getProject(projectId) });
  const projectFinance = useQuery({
    queryKey: ['project-finance', projectId],
    queryFn: () => getProjectFinance(projectId),
    enabled: canSeeMoney,
  });
  const employees = useQuery({
    queryKey: ['employees-options'],
    queryFn: () => getEmployees({ active_only: true, page_size: 100 }),
  });
  const clients = useQuery({ queryKey: ['clients-options'], queryFn: () => getClients({ page_size: 100 }) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    queryClient.invalidateQueries({ queryKey: ['projects'] });
  };

  const phaseMutation = useMutation({
    mutationFn: ({ phaseId, payload }: { phaseId: number; payload: Parameters<typeof updatePhase>[2] }) =>
      updatePhase(projectId, phaseId, payload),
    onSuccess: invalidate,
  });

  const teamMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role?: string }) => addTeamMember(projectId, userId, role),
    onSuccess: () => {
      setShowAddMember(false);
      invalidate();
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userId: number) => removeTeamMember(projectId, userId),
    onSuccess: invalidate,
  });

  const addPhaseMutation = useMutation({
    mutationFn: (payload: {
      name: string;
      start_date?: string | null;
      end_date?: string | null;
      studio_fee?: number | null;
      currency?: string;
      exchange_rate?: number;
    }) => addPhase(projectId, payload),
    onSuccess: invalidate,
  });

  const deletePhaseMutation = useMutation({
    mutationFn: (phaseId: number) => deletePhase(projectId, phaseId),
    onSuccess: invalidate,
  });

  const editMutation = useMutation({
    mutationFn: (payload: Partial<ProjectCreateInput>) => updateProject(projectId, payload),
    onSuccess: () => {
      setShowEdit(false);
      invalidate();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate('/projects');
    },
  });

  const data = project.data;

  // Financial data is executive-only (L0/L1) per the financial access policy.

  const canManage =
    canAccess(level, 'L2') ||
    (canAccess(level, 'L3') && data?.project_lead_id === user?.id);

  return (
    <div className="space-y-6">
      {project.isPending ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-3">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-4 w-48" />
            </div>
            <Skeleton className="h-9 w-32" />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : project.isError || !data ? (
        <EmptyState icon={FolderKanban} title={t('projects.projectNotFound')} />
      ) : (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <Breadcrumbs items={[{ label: 'Projects', to: '/projects' }, { label: data.name }]} />
              <h1 className="text-2xl font-bold tracking-tight text-ink">{data.name}</h1>
              <p className="mt-1 text-sm text-muted">
                {data.project_code} · {projectTypeLabel(data.project_type)}
              </p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <ProjectStatusBadge status={data.status} />
              <span className="text-xs text-muted">
                Priority · <span className="font-medium capitalize text-ink">{data.priority}</span>
              </span>
              {canManage && (
                <button onClick={() => setShowEdit(true)} className={secondaryBtnClass}>
                  <Pencil className="h-4 w-4" />
                  Edit project
                </button>
              )}
              {canAccess(level, 'L1') && (
                <button
                  onClick={() => setDeletingProject(true)}
                  disabled={deleteMutation.isPending}
                  className="inline-flex h-9 items-center gap-2 rounded-md border border-danger/30 bg-surface px-3 text-sm font-medium text-danger transition hover:bg-dangerSoft disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                  {deleteMutation.isPending ? t('common.deleting') : t('projects.deleteProject')}
                </button>
              )}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
              <p className="text-xs font-medium uppercase tracking-wide text-muted">{t('projects.progress')}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{data.progress_pct}%</p>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border/70">
                <div
                  className="h-full rounded-full bg-success transition-all"
                  style={{ width: `${Math.min(Number(data.progress_pct), 100)}%` }}
                />
              </div>
            </div>
            {canSeeMoney && (
              <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">{t('projects.studioFee')}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{formatCurrency(data.studio_fee, data.currency)}</p>
                <p className="mt-1 text-xs text-muted">Budget {formatCurrency(data.budget, data.currency)}</p>
              </div>
            )}
            <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
              <p className="text-xs font-medium uppercase tracking-wide text-muted">{t('projects.timeline')}</p>
              <p className="mt-1 text-sm font-medium text-ink">
                {data.start_date ?? '—'} → {data.end_date ?? '—'}
              </p>
              <p className="mt-1 flex items-center gap-1 text-xs text-muted">
                <MapPin className="h-3 w-3" />
                {data.location ?? 'No location set'}
              </p>
            </div>
          </div>

          {canSeeMoney && (
            <div className="rounded-lg border border-border bg-surface p-5 shadow-card">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">
                  Finance <span className="normal-case text-muted/70">· in INR</span>
                </p>
                {projectFinance.isFetching && (
                  <span className="text-xs text-muted/60">refreshing…</span>
                )}
              </div>
              {projectFinance.isError ? (
                <p className="mt-2 text-sm text-muted">Finance summary unavailable.</p>
              ) : projectFinance.data ? (
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  {[
                    { label: 'Invoiced', value: formatINR(projectFinance.data.invoiced), tone: 'text-info' },
                    { label: 'Received', value: formatINR(projectFinance.data.received), tone: 'text-success' },
                    { label: 'Outstanding', value: formatINR(projectFinance.data.outstanding), tone: 'text-warning' },
                    { label: 'Expenses', value: formatINR(projectFinance.data.expenses), tone: 'text-danger' },
                    { label: 'Profit', value: formatINR(projectFinance.data.profit), tone: 'text-ink' },
                  ].map((stat) => (
                    <div key={stat.label} className="rounded-md bg-surfaceWarm px-3 py-2">
                      <p className="text-[11px] font-medium uppercase tracking-wide text-muted">{stat.label}</p>
                      <p className={`mt-0.5 text-lg font-bold tabular-nums ${stat.tone}`}>{stat.value}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          <div className="flex flex-wrap gap-2 border-b border-border">
            {(
              [
                { key: 'overview', label: 'Overview', icon: Layers },
                { key: 'phases', label: `Phases (${data.phases.length})`, icon: GanttChart },
                { key: 'team', label: `Team (${data.team.length})`, icon: Users },
                { key: 'timeline', label: 'Timeline', icon: CalendarRange },
              ] as const
            ).map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition ${
                    tab === t.key
                      ? 'border-orange text-ink'
                      : 'border-transparent text-muted hover:text-ink'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {t.label}
                </button>
              );
            })}
          </div>

          {tab === 'overview' && <OverviewTab data={data} canSeeMoney={canSeeMoney} />}
          {tab === 'phases' && (
            <PhasesTab
              phases={data.phases}
              canManage={canManage}
              canSeeMoney={canSeeMoney}
              currency={data.currency}
              projectStart={data.start_date}
              projectEnd={data.end_date}
              onUpdatePhase={(phaseId, payload) => phaseMutation.mutate({ phaseId, payload })}
              onAddPhase={(payload) =>
                addPhaseMutation.mutate({
                  ...payload,
                  exchange_rate: data.exchange_rate ? Number(data.exchange_rate) : undefined,
                })
              }
              onDeletePhase={(phaseId) => setDeletingPhaseId(phaseId)}
              addPending={addPhaseMutation.isPending}
              addError={
                addPhaseMutation.isError
                  ? (addPhaseMutation.error as { response?: { data?: { detail?: string } } })?.response?.data
                      ?.detail ?? 'Could not add phase'
                  : null
              }
              updatePending={phaseMutation.isPending}
              deletePending={deletePhaseMutation.isPending}
            />
          )}
          {tab === 'team' && (
            <TeamTab
              members={data.team}
              canManage={canManage}
              employees={employees.data?.items ?? []}
              onAdd={(userId, role) => teamMutation.mutate({ userId, role })}
              onRemove={(userId) => removeMemberMutation.mutate(userId)}
              showAddMember={showAddMember}
              setShowAddMember={setShowAddMember}
              addPending={teamMutation.isPending}
            />
          )}
          {tab === 'timeline' && <TimelineTab projectId={projectId} start={data.start_date} end={data.end_date} />}
        </>
      )}

      {showEdit && data && (
        <EditProjectModal
          project={data}
          clients={(clients.data?.items ?? []).map((c) => ({ id: c.id, name: c.name }))}
          employees={(employees.data?.items ?? []).map((e) => ({ id: e.id, name: e.name }))}
          canAssignLead={canAccess(user?.org_level_code, 'L2')}
          canEditMoney={canSeeMoney}
          onClose={() => setShowEdit(false)}
          onSubmit={(payload) => editMutation.mutate(payload)}
          pending={editMutation.isPending}
          error={editMutation.error as { response?: { data?: { detail?: string } } } | null}
        />
      )}

      {deletingProject && (
        <ConfirmDialog
          title="Delete project?"
          message="This cannot be undone. All phases and team assignments will be removed."
          confirmLabel="Delete project"
          pending={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(undefined, { onSuccess: () => setDeletingProject(false) })}
          onClose={() => setDeletingProject(false)}
        />
      )}

      {deletingPhaseId !== null && (
        <ConfirmDialog
          title="Delete phase?"
          message="This cannot be undone. All phase data will be removed."
          confirmLabel="Delete phase"
          pending={deletePhaseMutation.isPending}
          onConfirm={() => deletePhaseMutation.mutate(deletingPhaseId, { onSuccess: () => setDeletingPhaseId(null) })}
          onClose={() => setDeletingPhaseId(null)}
        />
      )}
    </div>
  );
}



function OverviewTab({ data, canSeeMoney }: { data: ProjectDetail; canSeeMoney: boolean }) {
  const rows: [string, string][] = [
    ['Client', data.client_name ?? '—'],
    ['Project lead', data.lead_name ?? '—'],
    ['Category', data.category ?? '—'],
    ['Plot area', data.plot_area ?? '—'],
    ['Built-up area', data.built_up_area ?? '—'],
    ['Floors', data.no_of_floors ?? '—'],
    ...(canSeeMoney
      ? ([
          ['Fee type', data.fee_type ?? '—'],
          ['Fee %', data.fee_percent ?? '—'],
        ] as [string, string][])
      : []),
    ['Description', data.description ?? '—'],
  ];
  return (
    <div className="rounded-lg border border-border bg-surface shadow-card">
      {rows.map(([label, value], i) => (
        <div
          key={label}
          className={`grid grid-cols-[180px_1fr] gap-4 px-5 py-3 text-sm ${i !== rows.length - 1 ? 'border-b border-border' : ''}`}
        >
          <span className="text-muted">{label}</span>
          <span className="text-ink">{value}</span>
        </div>
      ))}
    </div>
  );
}

function PhasesTab({
  phases,
  canManage,
  canSeeMoney,
  currency = 'INR',
  projectStart,
  projectEnd,
  onUpdatePhase,
  onAddPhase,
  onDeletePhase,
  addPending,
  addError,
  updatePending,
  deletePending,
}: {
  phases: { id: number; name: string; order_index: number; start_date: string | null; end_date: string | null; status: PhaseStatus; completion_pct: string; studio_fee: string | null; currency?: string; exchange_rate?: string }[];
  canManage: boolean;
  canSeeMoney: boolean;
  currency?: string;
  projectStart?: string | null;
  projectEnd?: string | null;
  onUpdatePhase: (phaseId: number, payload: { name?: string; status?: PhaseStatus; completion_pct?: number | string; start_date?: string | null; end_date?: string | null; studio_fee?: number | null; currency?: string; exchange_rate?: number }) => void;
  onAddPhase: (payload: { name: string; start_date: string | null; end_date: string | null; studio_fee?: number | null; currency?: string }) => void;
  onDeletePhase: (phaseId: number) => void;
  addPending: boolean;
  addError?: string | null;
  updatePending: boolean;
  deletePending: boolean;
}) {
  const [newPhaseName, setNewPhaseName] = useState('');
  const [newPhaseFee, setNewPhaseFee] = useState('');
  const [newPhaseStart, setNewPhaseStart] = useState('');
  const [newPhaseEnd, setNewPhaseEnd] = useState('');
  const [phaseError, setPhaseError] = useState('');
  const [editing, setEditing] = useState<{
    id: number;
    name: string;
    status: PhaseStatus;
    start_date: string;
    end_date: string;
    completion_pct: number;
    studio_fee: string;
    currency: string;
    exchange_rate?: string;
  } | null>(null);

  return (
    <div className="space-y-3">
      {phases.map((p) => {
        const meta = phaseStatusMeta(p.status);
        const isLast = p.status === 'completed';
        const nextStatus = PHASE_FLOW[PHASE_FLOW.indexOf(p.status) + 1];
        return (
          <div key={p.id} className="rounded-lg border border-border bg-surface p-4 shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-navy/10 text-xs font-bold text-navy">
                  {p.order_index}
                </span>
                <div>
                  <p className="font-medium text-ink">{p.name}</p>
                  <p className="text-xs text-muted">
                    {p.start_date ?? '—'} → {p.end_date ?? '—'}
                    {canSeeMoney && p.studio_fee && <> · Studio fee {formatCurrency(p.studio_fee, p.currency)}</>}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.badge}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
                  {meta.label}
                </span>
                <span className="w-10 text-right text-sm font-semibold tabular-nums text-ink">{p.completion_pct}%</span>
                {canManage && (
                  <>
                    <button
                      onClick={() =>
                        onUpdatePhase(p.id, {
                          status: isLast ? 'in_progress' : nextStatus,
                          completion_pct: isLast ? 0 : 100,
                        })
                      }
                      className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted transition hover:bg-surfaceWarm hover:text-ink"
                    >
                      {isLast ? 'Reset' : 'Mark complete'}
                    </button>
                    <button
                      onClick={() =>
                        setEditing({
                          id: p.id,
                          name: p.name,
                          status: p.status,
                          start_date: p.start_date ?? '',
                          end_date: p.end_date ?? '',
                          completion_pct: Number(p.completion_pct) || 0,
                          studio_fee: p.studio_fee ?? '',
                          currency: p.currency ?? currency,
                          exchange_rate: p.exchange_rate,
                        })
                      }
                      title="Edit phase"
                      className="rounded-md border border-border bg-surface p-1.5 text-muted transition hover:bg-surfaceWarm hover:text-ink"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => onDeletePhase(p.id)}
                      disabled={deletePending}
                      title="Delete phase"
                      className="rounded-md border border-border bg-surface p-1.5 text-muted transition hover:border-danger/30 hover:bg-dangerSoft hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </>
                )}
              </div>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border/70">
              <div
                className={`h-full rounded-full transition-all ${PHASE_BAR_COLOR[p.status]}`}
                style={{ width: `${Math.min(Number(p.completion_pct), 100)}%` }}
              />
            </div>
          </div>
        );
      })}
      {canManage && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const name = newPhaseName.trim();
            if (!name || addPending) return;
            const start = newPhaseStart || null;
            const end = newPhaseEnd || null;
            if (start && end && start > end) {
              setPhaseError('Phase end date cannot be before its start date.');
              return;
            }
            if (projectStart && start && start < projectStart) {
              setPhaseError(`Phase cannot start before the project start date (${projectStart}).`);
              return;
            }
            if (projectStart && end && end < projectStart) {
              setPhaseError(`Phase cannot end before the project start date (${projectStart}).`);
              return;
            }
            if (projectEnd && start && start > projectEnd) {
              setPhaseError(`Phase cannot start after the project end date (${projectEnd}).`);
              return;
            }
            if (projectEnd && end && end > projectEnd) {
              setPhaseError(`Phase cannot end after the project end date (${projectEnd}).`);
              return;
            }
            onAddPhase({
              name,
              start_date: start,
              end_date: end,
              studio_fee: parseIndianCurrencyInput(newPhaseFee),
              currency,
            });
            setNewPhaseName('');
            setNewPhaseFee('');
            setNewPhaseStart('');
            setNewPhaseEnd('');
            setPhaseError('');
          }}
          className="rounded-lg border border-dashed border-border bg-surface p-4"
        >
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={newPhaseName}
              onChange={(e) => setNewPhaseName(e.target.value)}
              placeholder="New phase name…"
              className="h-10 min-w-40 flex-1 rounded-md border border-border bg-surface px-3 text-sm text-ink transition focus:border-navy focus:outline-none focus:ring-2 focus:ring-navy/30"
            />
            <div className="flex items-center gap-2">
              <DatePicker
                value={newPhaseStart}
                onChange={setNewPhaseStart}
                min={projectStart ?? undefined}
                max={newPhaseEnd || projectEnd || undefined}
                placeholder="Start date"
                className="w-36"
              />
              <span className="text-muted">→</span>
              <DatePicker
                value={newPhaseEnd}
                onChange={setNewPhaseEnd}
                min={newPhaseStart || projectStart || undefined}
                max={projectEnd ?? undefined}
                placeholder="End date"
                className="w-36"
              />
            </div>
            {canSeeMoney && (
              <CurrencyInput
                compact
                value={newPhaseFee}
                onChange={setNewPhaseFee}
                currency={currency}
                placeholder="Fee"
                className="w-32"
              />
            )}
            <button
              type="submit"
              disabled={addPending || !newPhaseName.trim()}
              className="inline-flex items-center gap-1 rounded-md bg-orange px-4 text-sm font-medium text-white transition hover:bg-orangeDark disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              Add phase
            </button>
          </div>
          {(projectStart || projectEnd || phaseError || addError) && (
            <div className="mt-2 flex min-h-4 items-center gap-3 text-xs">
              {projectStart || projectEnd ? (
                <span className="text-muted">
                  Project window: {projectStart ?? '—'} → {projectEnd ?? '—'}
                </span>
              ) : null}
              {(phaseError || addError) && <span className="text-danger">{phaseError || addError}</span>}
            </div>
          )}
        </form>
      )}

      {editing && (
        <PhaseEditModal
          phase={editing}
          pending={updatePending}
          canEditMoney={canSeeMoney}
          projectStart={projectStart}
          projectEnd={projectEnd}
          onClose={() => setEditing(null)}
          onSubmit={(payload) => {
            onUpdatePhase(editing.id, payload);
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}



function TeamTab({
  members,
  canManage,
  employees,
  onAdd,
  onRemove,
  showAddMember,
  setShowAddMember,
  addPending,
}: {
  members: { id: number; user_id: number; name: string; designation: string | null; role: string | null }[];
  canManage: boolean;
  employees: { id: number; name: string }[];
  onAdd: (userId: number, role?: string) => void;
  onRemove: (userId: number) => void;
  showAddMember: boolean;
  setShowAddMember: (v: boolean) => void;
  addPending: boolean;
}) {
  const [userId, setUserId] = useState<number | ''>('');
  const [role, setRole] = useState('');
  const already = new Set(members.map((m) => m.user_id));

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {members.map((m) => (
          <div key={m.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-4 shadow-card">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy/10 text-navy">
                <UserRound className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-ink">{m.name}</p>
                <p className="text-xs text-muted">{m.designation ?? '—'}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-graphite/10 px-2 py-0.5 text-xs font-medium text-muted">{m.role ?? 'member'}</span>
              {canManage && (
                <button
                  onClick={() => onRemove(m.user_id)}
                  title="Remove from team"
                  className="rounded-md p-1 text-muted transition hover:bg-dangerSoft hover:text-danger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        {members.length === 0 && (
          <div className="sm:col-span-2 lg:col-span-3">
            <EmptyState icon={UserRound} title="No team members yet." />
          </div>
        )}
      </div>

      {canManage &&
        (showAddMember ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (userId !== '') {
                onAdd(Number(userId), role || undefined);
              }
            }}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-3"
          >
            <select
              value={userId}
              onChange={(e) => setUserId(e.target.value === '' ? '' : Number(e.target.value))}
              className="min-w-48 flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink transition focus:border-navy focus:outline-none focus:ring-2 focus:ring-navy/30"
            >
              <option value="">Select employee…</option>
              {employees
                .filter((e) => !already.has(e.id))
                .map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name}
                  </option>
                ))}
            </select>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="Role (e.g. Architect)"
              className="w-48 rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink transition focus:border-navy focus:outline-none focus:ring-2 focus:ring-navy/30"
            />
            <button
              type="submit"
              disabled={addPending || userId === ''}
              className="inline-flex items-center gap-1 rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orangeDark disabled:cursor-not-allowed disabled:opacity-50"
            >
              Add
            </button>
            <button
              type="button"
              onClick={() => setShowAddMember(false)}
              className="rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium text-muted transition hover:bg-surfaceWarm hover:text-ink"
            >
              Cancel
            </button>
          </form>
        ) : (
          <button
            onClick={() => setShowAddMember(true)}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-muted transition hover:bg-surfaceWarm hover:text-ink"
          >
            <Plus className="h-4 w-4" />
            Add team member
          </button>
        ))}
    </div>
  );
}

function TimelineTab({ projectId, start, end }: { projectId: number; start: string | null; end: string | null }) {
  const timeline = useQuery({
    queryKey: ['timeline', projectId],
    queryFn: () => getProjectTimeline(projectId),
  });

  return <TimelineView start={start} end={end} timeline={timeline.data} loading={timeline.isPending} />;
}


