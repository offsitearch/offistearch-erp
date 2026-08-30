import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarDays, Flag, Megaphone, Pencil, Pin, Plus, StickyNote, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { createNotice, deleteNotice, getNotices, updateNotice } from '../../api/notices';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { EmptyState } from '../../components/ui/EmptyState';
import FormSection from '../../components/ui/FormSection';
import { LogoLoader } from '../../components/LogoLoader';
import DatePicker from '../../components/ui/DatePicker';
import { useToast } from '../../components/Toast';
import { noticeImportanceMeta, canAccess } from '../../lib/constants';
import { formatDate } from '../../lib/date';
import type { Notice, NoticeImportance, NoticeInput } from '../../lib/types';
import { useAuthStore } from '../../store/authStore';
import { inputClass, primaryBtnClass, secondaryBtnClass, modalLabelClass } from '../../lib/styles';
import { useTranslation } from 'react-i18next';

export default function NoticeBoardPage() {
  const { t } = useTranslation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isAdmin = canAccess(user?.org_level_code, 'L2');
  const [modal, setModal] = useState<{ editing?: Notice } | null>(null);
  const [deleting, setDeleting] = useState<Notice | null>(null);

  const notices = useQuery({
    queryKey: ['notices', isAdmin],
    queryFn: () => getNotices({ include_inactive: isAdmin }),
  });

  const toggleActive = useMutation({
    mutationFn: (notice: Notice) => updateNotice(notice.id, { is_active: !notice.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      toast(t('settings.noticeUpdated'), 'success');
    },
    onError: () => toast('Failed to update notice', 'error'),
  });

  const remove = useMutation({
    mutationFn: () => deleteNotice(deleting!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      toast(t('settings.noticeDeleted'), 'success');
      setDeleting(null);
    },
    onError: () => toast('Failed to delete notice', 'error'),
  });

  const sorted = [...(notices.data ?? [])].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t('nav.notices')}</h1>
           <p className="mt-1 text-sm text-muted">{t('notices.subtitle')}</p>
        </div>
        {isAdmin && (
          <button onClick={() => setModal({})} className={primaryBtnClass}>
            <Plus className="h-4 w-4" /> {t('settings.postNotice')}
          </button>
        )}
      </div>

      {notices.isPending ? (
        <LogoLoader />
      ) : sorted.length === 0 ? (
        <EmptyState
          title={t('settings.noNoticesYet')}
          text={t('settings.postFirstNotice')}
          icon={Megaphone}
        />
      ) : (
        <div className="space-y-3">
          {sorted.map((n) => {
            const meta = noticeImportanceMeta(n.importance);
            return (
              <div
                key={n.id}
                className={`rounded-xl border bg-surface p-5 shadow-card ${
                  n.is_pinned
                    ? 'border-orange/40 ring-1 ring-orange/20'
                    : 'border-border'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    {n.is_pinned && (
                      <Pin className="mt-1 h-4 w-4 shrink-0 fill-orange/60 text-orange" />
                    )}
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-base font-bold text-ink">{n.title}</h2>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${meta.badge}`}>
                          {meta.label}
                        </span>
                        {!n.is_active && isAdmin && (
                          <span className="rounded-full bg-surfaceWarm px-2 py-0.5 text-xs font-medium text-muted">
                            Inactive
                          </span>
                        )}
                      </div>
                      {n.body && <p className="mt-2 text-sm text-muted">{n.body}</p>}
                      <p className="mt-3 text-xs text-muted">
                        Posted {formatDate(n.created_at)}
                        {n.expiry_date ? ` · Expires ${formatDate(n.expiry_date)}` : ''}
                      </p>
                    </div>
                  </div>
                  {isAdmin && (
                    <div className="flex shrink-0 gap-1">
                      <button
                        onClick={() => setModal({ editing: n })}
                        className="rounded-lg p-1.5 text-muted transition hover:bg-surfaceWarm hover:text-ink"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setDeleting(n)}
                        aria-label="Delete notice"
                        className="rounded-lg p-1.5 text-muted transition hover:bg-dangerSoft hover:text-danger"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
                {isAdmin && (
                  <button
                    onClick={() => toggleActive.mutate(n)}
                    className="mt-3 text-xs font-medium text-muted underline-offset-2 hover:text-navy hover:underline"
                  >
                    {n.is_active ? t('common.deactivate') : t('settings.activate')}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {modal && <NoticeModal notice={modal.editing} onClose={() => setModal(null)} />}
      {deleting && (
        <ConfirmDialog
          title={t('settings.deleteNotice')}
          message={`"${deleting.title}" will be permanently removed.`}
          confirmLabel={t('common.delete')}
          pending={remove.isPending}
          onConfirm={() => remove.mutate()}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}

function NoticeModal({ notice, onClose }: { notice?: Notice; onClose: () => void }) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<NoticeInput>({
    title: notice?.title ?? '',
    body: notice?.body ?? '',
    importance: notice?.importance ?? 'medium',
    is_pinned: notice?.is_pinned ?? false,
    publish_date: notice?.publish_date ?? '',
    expiry_date: notice?.expiry_date ?? '',
  });

  const save = useMutation({
    mutationFn: () => {
      const payload: NoticeInput = {
        ...form,
        publish_date: form.publish_date || null,
        expiry_date: form.expiry_date || null,
      };
      return notice ? updateNotice(notice.id, payload) : createNotice(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      toast(notice ? t('settings.noticeUpdated') : t('settings.noticePublished'), 'success');
      onClose();
    },
    onError: () => toast('Failed to save notice', 'error'),
  });

  const IMPORTANCE_OPTIONS: NoticeImportance[] = ['low', 'medium', 'high'];
  const publishDate = (form.publish_date ?? '').slice(0, 10);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navyDark/40 p-4">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl border border-border bg-surface p-6 shadow-overlay">
        <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange/10 text-orange">
              <Megaphone className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-ink">
                {notice ? t('settings.editNotice') : t('settings.postNotice')}
              </h2>
              <p className="text-xs text-muted">
                {notice ? 'Update the notice and republish.' : 'Publish an announcement to the board.'}
              </p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-muted hover:bg-surfaceWarm hover:text-ink">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="mt-5 space-y-6">
          <FormSection icon={StickyNote} title="Notice">
            <label className={modalLabelClass}>
              Title *
              <input
                required
                autoFocus
                value={form.title}
                onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                placeholder="e.g. Office closure on Republic Day"
                className={`${inputClass} mt-1`}
              />
            </label>
            <label className={`${modalLabelClass} mt-3`}>
              Body
              <textarea
                rows={4}
                value={form.body ?? ''}
                onChange={(e) => setForm((p) => ({ ...p, body: e.target.value }))}
                placeholder="The details people need to read…"
                className={`${inputClass} mt-1 h-auto py-2`}
              />
            </label>
          </FormSection>

          <FormSection icon={Flag} title="Importance">
            <div className="grid grid-cols-3 gap-2">
              {IMPORTANCE_OPTIONS.map((imp) => {
                const meta = noticeImportanceMeta(imp);
                const active = form.importance === imp;
                return (
                  <button
                    key={imp}
                    type="button"
                    onClick={() => setForm((p) => ({ ...p, importance: imp }))}
                    aria-pressed={active}
                    className={`inline-flex h-10 items-center justify-center gap-2 rounded-md border text-sm font-medium transition ${
                      active
                        ? 'border-orange bg-orange/5 text-ink'
                        : 'border-border bg-surface text-ink hover:bg-surfaceWarm'
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
                    {meta.label}
                  </button>
                );
              })}
            </div>
          </FormSection>

          <FormSection icon={CalendarDays} title="Timing" hint="Leave these blank to show it immediately and never expire.">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className={modalLabelClass}>
                Publish date
                <DatePicker
                  value={publishDate}
                  onChange={(v) => setForm((p) => ({ ...p, publish_date: v }))}
                  className="mt-1"
                />
              </label>
              <label className={modalLabelClass}>
                Expiry date
                <DatePicker
                  value={(form.expiry_date ?? '').slice(0, 10)}
                  min={publishDate || undefined}
                  onChange={(v) => setForm((p) => ({ ...p, expiry_date: v }))}
                  className="mt-1"
                />
              </label>
            </div>
            <label className="mt-3 flex cursor-pointer items-center gap-3 rounded-lg border border-border bg-surface p-3 transition hover:bg-surfaceWarm">
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition ${
                  form.is_pinned ? 'bg-orange/10 text-orange' : 'bg-graphite/10 text-graphite'
                }`}
              >
                <Pin className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-ink">Pin to top</span>
                <span className="block text-xs text-muted">Pinned notices stay pinned at the top of the board.</span>
              </span>
              <input
                type="checkbox"
                checked={form.is_pinned}
                onChange={(e) => setForm((p) => ({ ...p, is_pinned: e.target.checked }))}
                className="h-4 w-4 rounded border-border accent-orange"
              />
            </label>
          </FormSection>

          <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted">Title is required.</p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={onClose} className={secondaryBtnClass}>
                Cancel
              </button>
              <button
                type="submit"
                disabled={save.isPending || !form.title.trim()}
                className={`${primaryBtnClass} min-w-[10rem]`}
              >
                {notice ? t('common.save') : t('settings.publishNotice')}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
