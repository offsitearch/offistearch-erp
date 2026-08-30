import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarDays, Camera, Clock, Download, Edit3, HardHat, MapPin, Plus, StickyNote, Sun, Trash2, Users, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getProjects } from '../../api/projects';
import {
  createSiteVisit,
  deleteSiteVisit,
  deleteSiteVisitPhoto,
  getSiteVisitPhoto,
  getSiteVisits,
  siteVisitReportUrl,
  updateSiteVisit,
  uploadSiteVisitPhoto,
} from '../../api/siteVisits';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { LogoLoader } from '../../components/LogoLoader';
import { Skeleton } from '../../components/ui/Skeleton';
import DatePicker from '../../components/ui/DatePicker';
import TimeInput from '../../components/ui/TimeInput';
import { useToast } from '../../components/Toast';
import { projectStatusMeta, siteVisitStatusMeta, canAccess } from '../../lib/constants';
import { formatDate, formatTime } from '../../lib/date';
import type {
  ProjectListItem,
  SiteVisit,
  SiteVisitInput,
  SiteVisitPhoto,
  SiteVisitStatus,
} from '../../lib/types';
import { useAuthStore } from '../../store/authStore';
import { inputClass, selectClass, primaryBtnClass, secondaryBtnClass, dangerBtnClass, modalLabelClass } from '../../lib/styles';
import FormSection from '../../components/ui/FormSection';
import { useTranslation } from 'react-i18next';

const successBtnClass =
  'inline-flex h-10 items-center justify-center gap-2 rounded-md bg-success px-4 text-sm font-medium text-white transition hover:bg-successDark focus:outline-none focus:ring-2 focus:ring-success/40 disabled:cursor-not-allowed disabled:opacity-60';

export default function SiteVisitsPage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const canCreate = canAccess(user?.org_level_code, 'L3');
  const [statusFilter, setStatusFilter] = useState<SiteVisitStatus | 'all'>('all');
  const [creating, setCreating] = useState(false);

  const visits = useQuery({
    queryKey: ['site-visits', statusFilter],
    queryFn: () => getSiteVisits({ status: statusFilter === 'all' ? undefined : statusFilter }),
    staleTime: 60_000,
  });

  const filtered =
    statusFilter === 'all'
      ? visits.data ?? []
      : (visits.data ?? []).filter((v) => v.status === statusFilter);

  const sorted = [...filtered].sort((a, b) => new Date(b.visit_date).getTime() - new Date(a.visit_date).getTime());

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t('siteVisits.title')}</h1>
           <p className="mt-1 text-sm text-muted">{t('siteVisits.trackOnSite')}</p>
        </div>
        {canCreate && (
          <button onClick={() => setCreating(true)} className={primaryBtnClass}>
            <Plus className="h-4 w-4" /> {t('siteVisits.logVisit')}
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {(['all', 'scheduled', 'completed', 'cancelled'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium capitalize transition ${
              statusFilter === s
                ? 'bg-orange text-white'
                : 'border border-border bg-surface text-muted hover:bg-surfaceWarm'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {visits.isPending ? (
        <LogoLoader />
      ) : sorted.length === 0 ? (
        <EmptyState
          title={t('siteVisits.noSiteVisits')}
          text={t('siteVisits.noSiteVisitsText')}
          icon={HardHat}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {sorted.map((v) => (
            <SiteVisitCard key={v.id} visit={v} canCreate={canCreate} />
          ))}
        </div>
      )}

      {creating && <SiteVisitFormModal onClose={() => setCreating(false)} />}
    </div>
  );
}

function SiteVisitCard({ visit, canCreate }: { visit: SiteVisit; canCreate: boolean }) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isAdmin = canAccess(user?.org_level_code, 'L2');
  const canManage = canCreate || isAdmin;
  const fileRef = useRef<HTMLInputElement>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const [lightbox, setLightbox] = useState<{ url: string; caption: string | null } | null>(null);

  const status = siteVisitStatusMeta(visit.status);

  const markCompleted = useMutation({
    mutationFn: () => updateSiteVisit(visit.id, { status: 'completed' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['site-visits'] });
      toast(t('siteVisits.visitMarkedCompleted'), 'success');
    },
    onError: () => toast('Failed to update visit', 'error'),
  });

  const cancelVisit = useMutation({
    mutationFn: () => updateSiteVisit(visit.id, { status: 'cancelled' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['site-visits'] });
      toast(t('siteVisits.visitCancelled'), 'success');
    },
    onError: () => toast('Failed to cancel visit', 'error'),
  });

  const upload = useMutation({
    mutationFn: (file: File) => uploadSiteVisitPhoto(visit.id, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['site-visits'] });
      toast(t('siteVisits.photoUploaded'), 'success');
    },
    onError: () => toast('Photo upload failed', 'error'),
  });

  const remove = useMutation({
    mutationFn: () => deleteSiteVisit(visit.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['site-visits'] });
      toast(t('siteVisits.siteVisitDeleted'), 'success');
      setConfirmDelete(false);
    },
    onError: () => toast('Failed to delete visit', 'error'),
  });

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) upload.mutate(file);
    e.target.value = '';
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted">
            {visit.project_name ? visit.project_name : visit.project_code ?? t('siteVisits.generalSiteVisit')}
          </p>
          <h3 className="mt-0.5 text-base font-bold text-ink">{visit.purpose || t('siteVisits.siteVisit')}</h3>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
            <span className={`rounded-full px-2 py-0.5 font-medium ${status.badge}`}>{status.label}</span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" /> {visit.location ?? t('siteVisits.locationNotSet')}
            </span>
            {visit.weather && <span>{visit.weather}</span>}
          </div>
        </div>
        {canManage && (
          <div className="flex gap-1">
            <button
              onClick={() => setEditing(true)}
              className="rounded-lg p-1.5 text-muted transition hover:bg-surfaceWarm hover:text-ink"
              title={t('common.edit')}
            >
              <Edit3 className="h-4 w-4" />
            </button>
            <button
              onClick={() => setConfirmDelete(true)}
              className="rounded-lg p-1.5 text-muted transition hover:bg-dangerSoft hover:text-danger"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      <p className="mt-3 text-sm text-muted">
        {formatDate(visit.visit_date)}
        {visit.start_time || visit.end_time ? ` · ${formatTime(visit.start_time)}–${formatTime(visit.end_time)}` : ''}
        {visit.creator_name ? ` · logged by ${visit.creator_name}` : ''}
      </p>

      {visit.notes && <p className="mt-3 rounded-lg bg-surfaceWarm px-3 py-2 text-sm text-muted">{visit.notes}</p>}

      {visit.attendance_notes && (
        <p className="mt-2 text-xs text-muted">
          <span className="font-medium">Attendance:</span> {visit.attendance_notes}
        </p>
      )}

      {visit.photos.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {visit.photos.map((p) => (
            <SiteVisitPhoto
              key={p.id}
              visitId={visit.id}
              photo={p}
              canManage={canManage}
              onLightbox={(url, caption) => setLightbox({ url, caption })}
            />
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onFile} />
        {canManage && (
          <button
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
            className={secondaryBtnClass}
            style={{ height: '32px', fontSize: '12px' }}
          >
            <Camera className="h-3.5 w-3.5" /> {t('siteVisits.addPhoto')}
          </button>
        )}
        <a
          href={siteVisitReportUrl(visit.id)}
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface px-3 text-xs font-medium text-ink transition hover:bg-surfaceWarm"
        >
          <Download className="h-3.5 w-3.5" /> {t('siteVisits.pdfReport')}
        </a>
        {visit.status === 'scheduled' && canManage && (
          <>
            <button
              onClick={() => markCompleted.mutate()}
              disabled={markCompleted.isPending}
              className={`${successBtnClass} ml-auto`}
            >
              Mark completed
            </button>
            <button
              onClick={() => cancelVisit.mutate()}
              disabled={cancelVisit.isPending}
              className={dangerBtnClass}
            >
              Cancel
            </button>
          </>
        )}
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title={t('siteVisits.deleteTitle')}
          message={`"${visit.purpose || 'This site visit'}" and its photos will be permanently removed.`}
          confirmLabel={t('common.delete')}
          pending={remove.isPending}
          onConfirm={() => remove.mutate()}
          onClose={() => setConfirmDelete(false)}
        />
      )}

      {lightbox && (
        <div
          className="fixed inset-0 z-[60] flex flex-col items-center justify-center bg-navyDark/80 p-4"
          onClick={() => setLightbox(null)}
        >
          <button
            onClick={() => setLightbox(null)}
            aria-label="Close lightbox"
            className="absolute right-4 top-4 rounded-lg bg-surface/80 p-2 text-ink hover:bg-surface"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={lightbox.url}
            alt={lightbox.caption ?? t('siteVisits.photoAlt')}
            className="max-h-[80vh] max-w-[90vw] rounded-lg object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          {lightbox.caption && (
            <p className="mt-3 max-w-[90vw] text-center text-sm text-white/80">{lightbox.caption}</p>
          )}
        </div>
      )}

      {editing && <SiteVisitFormModal visit={visit} onClose={() => setEditing(false)} />}
    </div>
  );
}

function SiteVisitPhoto({
  visitId,
  photo,
  canManage,
  onLightbox,
}: {
  visitId: number;
  photo: SiteVisitPhoto;
  canManage: boolean;
  onLightbox: (url: string, caption: string | null) => void;
}) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const removePhoto = useMutation({
    mutationFn: () => deleteSiteVisitPhoto(visitId, photo.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['site-visits'] });
      toast(t('siteVisits.photoDeleted'), 'success');
    },
    onError: () => toast('Failed to delete photo', 'error'),
  });

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    getSiteVisitPhoto(visitId, photo.id)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [visitId, photo.id]);

  if (failed) return <div className="h-16 w-16 rounded-lg bg-surfaceWarm" title={t('siteVisits.photoUnavailable')} />;
  if (!url) return <Skeleton className="h-16 w-16 rounded-lg" />;
  return (
    <div className="group relative">
      <img
        src={url}
        alt={photo.caption ?? t('siteVisits.photoAlt')}
        className="h-16 w-16 cursor-pointer rounded-lg object-cover transition hover:opacity-80"
        onClick={() => onLightbox(url, photo.caption ?? null)}
      />
      {canManage && (
        <button
          onClick={() => removePhoto.mutate()}
          disabled={removePhoto.isPending}
          className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-danger text-[10px] text-white opacity-0 transition group-hover:opacity-100"
          title={t('common.delete')}
        >
          ×
        </button>
      )}
    </div>
  );
}

function SiteVisitFormModal({
  onClose,
  visit,
}: {
  onClose: () => void;
  visit?: SiteVisit | null;
}) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isEdit = !!visit;

  const projects = useQuery({
    queryKey: ['projects-light'],
    queryFn: () => getProjects({ page_size: 100 }),
    enabled: !!user,
  });

  const [form, setForm] = useState<SiteVisitInput>({
    project_id: visit?.project_id ?? 0,
    visit_date: visit?.visit_date ?? new Date().toISOString().slice(0, 10),
    start_time: visit?.start_time ?? '',
    end_time: visit?.end_time ?? '',
    purpose: visit?.purpose ?? '',
    notes: visit?.notes ?? '',
    location: visit?.location ?? '',
    weather: visit?.weather ?? '',
    attendance_notes: visit?.attendance_notes ?? '',
  });

  const save = useMutation({
    mutationFn: () => {
      const payload = { ...form, project_id: Number(form.project_id) };
      return isEdit ? updateSiteVisit(visit.id, payload) : createSiteVisit(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['site-visits'] });
      toast(isEdit ? t('siteVisits.siteVisitUpdated') : t('siteVisits.siteVisitLogged'), 'success');
      onClose();
    },
    onError: (err) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? `Failed to ${isEdit ? 'update' : 'log'} visit`, 'error');
    },
  });

  function set<K extends keyof SiteVisitInput>(key: K, value: SiteVisitInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  const projectsList = (projects.data as unknown as { results: ProjectListItem[] } | undefined)?.results ?? [];
  const selectedProject = projectsList.find((p) => p.id === form.project_id);

  const durationText = (() => {
    if (!form.start_time || !form.end_time) return null;
    const [sh, sm] = form.start_time.split(':').map((n) => Number(n));
    const [eh, em] = form.end_time.split(':').map((n) => Number(n));
    let total = eh * 60 + em - (sh * 60 + sm);
    if (total < 0) total += 24 * 60;
    const h = Math.floor(total / 60);
    const m = total % 60;
    if (h === 0) return `${m}m`;
    return m > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${h}h`;
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navyDark/40 p-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl border border-border bg-surface p-6 shadow-overlay">
        <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange/10 text-orange">
              <HardHat className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-ink">{isEdit ? t('siteVisits.editVisit') : t('siteVisits.logVisit')}</h2>
              <p className="text-xs text-muted">Record the purpose, timing and site details of the visit.</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-muted hover:bg-surfaceWarm hover:text-ink">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="mt-5 space-y-6">
          <FormSection icon={HardHat} title="Project" hint={selectedProject ? `${selectedProject.project_code} · ${selectedProject.client_name ?? 'No client'}` : undefined}>
            <label className={modalLabelClass}>
              Project *
              <select
                required
                value={form.project_id}
                onChange={(e) => set('project_id', Number(e.target.value))}
                disabled={projects.isPending}
                className={`${selectClass} mt-1`}
              >
                <option value={0} disabled>
                  {projects.isPending ? 'Loading projects…' : t('siteVisits.selectProject')}
                </option>
                {projectsList.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.project_code} — {p.name}
                  </option>
                ))}
              </select>
            </label>
            {selectedProject && (
              <div className="mt-2 rounded-lg border border-border bg-surfaceWarm/60 p-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-orange/10 text-orange">
                    <HardHat className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-ink">{selectedProject.name}</span>
                    <span className="block truncate text-xs text-muted">{selectedProject.client_name ?? 'No client linked'}</span>
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${projectStatusMeta(selectedProject.status).badge}`}>
                    {projectStatusMeta(selectedProject.status).label}
                  </span>
                </div>
                {(selectedProject.location || selectedProject.lead_name) && (
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-2 text-xs text-muted">
                    {selectedProject.location && (
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" /> {selectedProject.location}
                      </span>
                    )}
                    {selectedProject.lead_name && (
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" /> {selectedProject.lead_name}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}
          </FormSection>

          <FormSection icon={CalendarDays} title="Schedule">
            <label className={modalLabelClass}>
              {t('siteVisits.purpose')} *
              <input
                required
                autoFocus
                value={form.purpose ?? ''}
                onChange={(e) => set('purpose', e.target.value)}
                placeholder="e.g. Foundation inspection, survey with client…"
                className={`${inputClass} mt-1`}
              />
            </label>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <label className={modalLabelClass}>
                {t('siteVisits.visitDate')} *
                <DatePicker
                  value={form.visit_date}
                  onChange={(v) => set('visit_date', v)}
                  className="mt-1"
                />
              </label>
              <label className={modalLabelClass}>
                Start time
                <TimeInput
                  value={form.start_time ?? ''}
                  onChange={(v) => set('start_time', v)}
                  className="mt-1"
                />
              </label>
              <label className={modalLabelClass}>
                End time
                <TimeInput
                  value={form.end_time ?? ''}
                  onChange={(v) => set('end_time', v)}
                  className="mt-1"
                />
              </label>
            </div>
            {durationText && (
              <p className="mt-2.5 inline-flex items-center gap-1.5 rounded-full bg-successSoft px-2.5 py-1 text-xs font-semibold text-success">
                <Clock className="h-3.5 w-3.5" />
                Duration {durationText}
              </p>
            )}
          </FormSection>

          <FormSection icon={MapPin} title="Site & weather">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className={modalLabelClass}>
                Location
                <input
                  value={form.location ?? ''}
                  onChange={(e) => set('location', e.target.value)}
                  placeholder="Site address / landmark"
                  className={`${inputClass} mt-1`}
                />
              </label>
              <label className={modalLabelClass}>
                Weather
                <div className="relative mt-1">
                  <Sun className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                  <input
                    value={form.weather ?? ''}
                    onChange={(e) => set('weather', e.target.value)}
                    placeholder={t('siteVisits.weatherPlaceholder')}
                    className={`${inputClass} pl-9`}
                  />
                </div>
              </label>
            </div>
          </FormSection>

          <FormSection icon={StickyNote} title="Notes">
            <label className={modalLabelClass}>
              Notes
              <textarea
                rows={3}
                value={form.notes ?? ''}
                onChange={(e) => set('notes', e.target.value)}
                placeholder="Observations, measurements, decisions taken on site…"
                className={`${inputClass} mt-1 h-auto py-2`}
              />
            </label>
            <label className={`${modalLabelClass} mt-3`}>
              Attendance notes
              <textarea
                rows={2}
                value={form.attendance_notes ?? ''}
                onChange={(e) => set('attendance_notes', e.target.value)}
                placeholder={t('siteVisits.attendanceNotesPlaceholder')}
                className={`${inputClass} mt-1 h-auto py-2`}
              />
            </label>
          </FormSection>

          <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted">Fields marked * are required.</p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={onClose} className={secondaryBtnClass}>
                Cancel
              </button>
              <button
                type="submit"
                disabled={save.isPending || !form.purpose || !form.visit_date || form.project_id === 0}
                className={`${primaryBtnClass} min-w-[10rem]`}
              >
                {isEdit ? t('common.save') : t('siteVisits.logVisit')}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
