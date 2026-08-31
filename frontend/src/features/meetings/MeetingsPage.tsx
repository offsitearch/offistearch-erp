import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { LucideIcon } from 'lucide-react';
import {
  Briefcase,
  Building2,
  CalendarDays,
  Check,
  Clock,
  Loader2,
  MapPin,
  Plus,
  Search,
  Users,
  Video,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { createMeeting, deleteMeeting, getMeetings, rsvpMeeting, updateMeeting } from '../../api/meetings';
import { getUsers } from '../../api/settings';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { EmptyState } from '../../components/ui/EmptyState';
import FormSection from '../../components/ui/FormSection';
import { Skeleton } from '../../components/ui/Skeleton';
import { useToast } from '../../components/Toast';
import DatePicker from '../../components/ui/DatePicker';
import TimeInput from '../../components/ui/TimeInput';
import { MEETING_TYPE_OPTIONS, LEVEL_BADGE, meetingStatusMeta, meetingTypeLabel, canAccess } from '../../lib/constants';
import type { Meeting, MeetingInput, MeetingType, RsvpStatus } from '../../lib/types';
import { useAuthStore } from '../../store/authStore';
import { inputClass, primaryBtnClass, secondaryBtnClass, dangerBtnClass, modalLabelClass } from '../../lib/styles';
import { toISODate } from '../../lib/date';
import { useTranslation } from 'react-i18next';

export default function MeetingsPage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const canCreate = canAccess(user?.org_level_code, 'L3');
  const [creating, setCreating] = useState(false);

  const meetings = useQuery({ queryKey: ['meetings'], queryFn: getMeetings });

  const upcoming = (meetings.data ?? [])
    .filter((m) => m.status === 'scheduled')
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t('meetings.title')}</h1>
           <p className="mt-1 text-sm text-muted">{t('meetings.scheduleStudioSyncs')}, client reviews and site visits.</p>
        </div>
        {canCreate && (
          <button onClick={() => setCreating(true)} className={primaryBtnClass}>
            <Plus className="h-4 w-4" /> Schedule Meeting
          </button>
        )}
      </div>

      {meetings.isPending ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-52 w-full rounded-xl" />
          ))}
        </div>
      ) : upcoming.length === 0 ? (
        <EmptyState
          title={t('meetings.noUpcomingMeetings')}
          text={t('meetings.scheduledAppearHere')}
          icon={CalendarDays}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {upcoming.map((m) => (
            <MeetingCard key={m.id} meeting={m} />
          ))}
        </div>
      )}

      {creating && <MeetingFormModal onClose={() => setCreating(false)} />}
    </div>
  );
}

function MeetingCard({ meeting }: { meeting: Meeting }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const canManage = canAccess(user?.org_level_code, 'L3') || meeting.organizer_id === user?.id;
  const [confirmDelete, setConfirmDelete] = useState(false);

  const respond = useMutation({
    mutationFn: (status: RsvpStatus) => rsvpMeeting(meeting.id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      toast('RSVP updated', 'success');
    },
    onError: (err) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? 'Failed to update RSVP', 'error');
    },
  });

  const markComplete = useMutation({
    mutationFn: () => updateMeeting(meeting.id, { status: 'completed' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      toast('Meeting marked complete', 'success');
    },
    onError: () => toast('Failed to update meeting', 'error'),
  });

  const remove = useMutation({
    mutationFn: () => deleteMeeting(meeting.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      toast('Meeting deleted', 'success');
    },
    onError: () => toast('Failed to delete meeting', 'error'),
  });

  const when = new Date(meeting.scheduled_at);
  const status = meetingStatusMeta(meeting.status);

  return (
    <div className="flex flex-col rounded-xl border border-border bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex flex-col items-center rounded-lg bg-navy/10 px-3 py-2 text-navy">
            <span className="text-lg font-bold leading-none">
              {when.toLocaleDateString('en-IN', { day: '2-digit' })}
            </span>
            <span className="text-[10px] font-semibold uppercase">
              {when.toLocaleDateString('en-IN', { month: 'short' })}
            </span>
          </div>
          <div>
            <h3 className="font-bold text-ink">{meeting.title}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="rounded-full bg-surfaceWarm px-2 py-0.5 font-medium text-graphite">
                {meetingTypeLabel(meeting.meeting_type)}
              </span>
              <span className={`rounded-full px-2 py-0.5 font-medium ${status.badge}`}>{status.label}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-1.5 text-sm text-muted">
        <p className="flex items-center gap-2">
          <Clock className="h-3.5 w-3.5" />
          {when.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} · {meeting.duration_minutes} min
        </p>
        {meeting.location && (
          <p className="flex items-center gap-2">
            <MapPin className="h-3.5 w-3.5" /> {meeting.location}
          </p>
        )}
        {meeting.meeting_link && (
          <p className="flex items-center gap-2">
            <Video className="h-3.5 w-3.5" /> {meeting.meeting_link}
          </p>
        )}
        <p className="flex items-center gap-2">
          <Users className="h-3.5 w-3.5" />
          {meeting.attendees.length === 0
            ? 'No attendees yet'
            : `${meeting.attendees.length} attending · ${meeting.organizer_name ?? 'you'} (organizer)`}
        </p>
      </div>

      {meeting.description && (
        <p className="mt-3 rounded-lg bg-surfaceWarm px-3 py-2 text-sm text-muted">
          {meeting.description}
        </p>
      )}

      {meeting.my_rsvp && meeting.my_rsvp !== 'pending' && (
        <div className="mt-3 text-xs font-medium text-muted">
          You RSVP'd: <span className="capitalize">{meeting.my_rsvp}</span>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {meeting.my_rsvp === 'pending' ? (
          <>
            <button
              onClick={() => respond.mutate('accepted')}
              disabled={respond.isPending}
              className="inline-flex h-8 items-center gap-1.5 rounded-md bg-success px-3 text-xs font-medium text-white transition hover:bg-success/90 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" /> Accept
            </button>
            <button
              onClick={() => respond.mutate('declined')}
              disabled={respond.isPending}
              className={secondaryBtnClass}
              style={{ height: '32px', fontSize: '12px' }}
            >
              <X className="h-3.5 w-3.5" /> Decline
            </button>
          </>
        ) : (
          <span className="text-xs text-muted">RSVP sent</span>
        )}
        {canManage && meeting.status === 'scheduled' && (
          <button
            onClick={() => markComplete.mutate()}
            className={secondaryBtnClass}
            style={{ height: '32px', fontSize: '12px', marginLeft: 'auto' }}
          >
            Mark complete
          </button>
        )}
        {canManage && (
          <button
            onClick={() => setConfirmDelete(true)}
            className={dangerBtnClass}
            style={{ height: '32px', fontSize: '12px' }}
          >
            Cancel
          </button>
        )}
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title="Cancel meeting?"
          message={`"${meeting.title}" will be cancelled and removed.`}
          confirmLabel="Cancel meeting"
          pending={remove.isPending}
          onConfirm={() => {
            remove.mutate(undefined, {
              onSuccess: () => setConfirmDelete(false),
            });
          }}
          onClose={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}

const MEETING_TYPE_META: Record<MeetingType, { label: string; icon: LucideIcon }> = {
  internal: { label: 'Internal', icon: Users },
  client: { label: 'Client', icon: Briefcase },
  site: { label: 'Site', icon: Building2 },
  video: { label: 'Video call', icon: Video },
};

const DURATION_PRESETS = [15, 30, 60, 90, 120];

function nextHalfHourSlot(): string {
  const d = new Date();
  const mins = d.getMinutes();
  const next = mins <= 45 ? (mins <= 15 ? 30 : 60) : 30;
  d.setMinutes(next === 60 ? 0 : next, 0, 0);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${toISODate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

function MeetingFormModal({ onClose }: { onClose: () => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);

  const users = useQuery({
    queryKey: ['meeting-attendees'],
    queryFn: () => getUsers({ active_only: true }),
    enabled: !!user,
    retry: false,
  });

  // scheduled_at holds the raw local "YYYY-MM-DDTHH:mm" while editing and is
  // converted to a UTC ISO string only on submit — datetime pickers must never
  // receive a "Z" suffixed value or they stop matching/persisting.
  const [form, setForm] = useState<MeetingInput>({
    title: '',
    description: '',
    meeting_type: 'internal',
    scheduled_at: nextHalfHourSlot(),
    duration_minutes: 60,
    location: '',
    meeting_link: '',
    attendee_ids: [],
  });
  const [attendeeSearch, setAttendeeSearch] = useState('');

  const save = useMutation({
    mutationFn: () =>
      createMeeting({ ...form, scheduled_at: new Date(form.scheduled_at).toISOString() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] });
      toast('Meeting scheduled', 'success');
      onClose();
    },
    onError: () => toast('Failed to schedule meeting', 'error'),
  });

  function set<K extends keyof MeetingInput>(key: K, value: MeetingInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleAttendee(id: number) {
    set(
      'attendee_ids',
      (form.attendee_ids ?? []).includes(id)
        ? (form.attendee_ids ?? []).filter((x) => x !== id)
        : [...(form.attendee_ids ?? []), id],
    );
  }

  const date = form.scheduled_at.slice(0, 10);
  const time = form.scheduled_at.slice(11, 16);
  const hasSlot = !!date && !!time;
  const canSchedule = !!form.title.trim() && hasSlot;

  const endAt = hasSlot
    ? new Date(new Date(`${date}T${time}`).getTime() + (form.duration_minutes ?? 60) * 60000)
    : null;

  const people = (users.data ?? []).filter((u) => u.id !== user?.id);
  const query = attendeeSearch.trim().toLowerCase();
  const filtered = query
    ? people.filter((u) => `${u.name} ${u.designation ?? ''}`.toLowerCase().includes(query))
    : people;
  const attendees = (form.attendee_ids ?? []);
  const selectedSet = new Set(attendees);
  const selectedPeople = people.filter((u) => selectedSet.has(u.id));

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
              <CalendarDays className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-ink">Schedule meeting</h2>
              <p className="text-xs text-muted">Pick a slot, invite people, everyone gets notified.</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-muted hover:bg-surfaceWarm hover:text-ink">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="mt-5 space-y-6">
          <FormSection icon={Clock} title="When">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className={modalLabelClass}>
                Date *
                <DatePicker
                  value={date}
                  min={toISODate(new Date())}
                  onChange={(d) => set('scheduled_at', `${d}T${time || '10:00'}`)}
                  className="mt-1"
                />
              </label>
              <label className={modalLabelClass}>
                Start time *
                <TimeInput
                  value={time}
                  onChange={(t) => set('scheduled_at', `${date || toISODate(new Date())}T${t}`)}
                  className="mt-1"
                />
              </label>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-muted">Duration</span>
              <div className="flex flex-wrap gap-1.5">
                {DURATION_PRESETS.map((mins) => {
                  const active = form.duration_minutes === mins;
                  return (
                    <button
                      key={mins}
                      type="button"
                      onClick={() => set('duration_minutes', mins)}
                      className={`h-8 rounded-md border px-3 text-xs font-semibold transition ${
                        active
                          ? 'border-orange bg-orange/5 text-ink'
                          : 'border-border bg-surface text-ink hover:bg-surfaceWarm'
                      }`}
                    >
                      {mins}m
                    </button>
                  );
                })}
              </div>
              {endAt && (
                <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-successSoft px-2.5 py-1 text-xs font-semibold text-success">
                  <Check className="h-3.5 w-3.5" />
                  Ends {endAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          </FormSection>

          <FormSection icon={Video} title="Meeting">
            <label className={modalLabelClass}>
              Title *
              <input
                required
                autoFocus
                value={form.title}
                onChange={(e) => set('title', e.target.value)}
                placeholder="e.g. Weekly design sync"
                className={`${inputClass} mt-1`}
              />
            </label>
            <div className="mt-3">
              <span className="mb-1.5 block text-xs font-medium text-muted">Type</span>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {MEETING_TYPE_OPTIONS.map((mt) => {
                  const meta = MEETING_TYPE_META[mt];
                  const Icon = meta.icon;
                  const active = form.meeting_type === mt;
                  return (
                    <button
                      key={mt}
                      type="button"
                      onClick={() => set('meeting_type', mt)}
                      aria-pressed={active}
                      className={`inline-flex h-10 items-center justify-center gap-2 rounded-md border text-sm font-medium transition ${
                        active
                          ? 'border-orange bg-orange/5 text-ink'
                          : 'border-border bg-surface text-ink hover:bg-surfaceWarm'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      {meta.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <label className={`${modalLabelClass} mt-3`}>
              Description
              <textarea
                rows={2}
                value={form.description ?? ''}
                onChange={(e) => set('description', e.target.value)}
                placeholder="Agenda, context, anything the team should know before they join…"
                className={`${inputClass} mt-1 h-auto py-2`}
              />
            </label>
          </FormSection>

          <FormSection icon={MapPin} title="Where & how">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className={modalLabelClass}>
                Location
                <input
                  value={form.location ?? ''}
                  onChange={(e) => set('location', e.target.value)}
                  placeholder="Room / office / site address"
                  className={`${inputClass} mt-1`}
                />
              </label>
              <label className={modalLabelClass}>
                Video / meeting link
                <input
                  value={form.meeting_link ?? ''}
                  onChange={(e) => set('meeting_link', e.target.value)}
                  placeholder="https://…"
                  className={`${inputClass} mt-1`}
                />
              </label>
            </div>
          </FormSection>

          <FormSection icon={Users} title="Attendees" hint={`${selectedPeople.length} selected`}>
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="flex items-center gap-3 border-b border-border bg-surfaceWarm/60 px-3 py-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-[#C9964A]/20 bg-azure text-[11px] font-bold text-white shadow-sm">
                  {user ? user.name.split(' ').map((p) => p[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() : '?'}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">
                    {user?.name ?? 'You'}
                    <span className="ml-1.5 text-xs font-normal text-muted">(organizer)</span>
                  </span>
                  <span className="block truncate text-xs text-muted">{user?.designation ?? '—'}</span>
                </span>
                <span className="rounded-full bg-navy/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-navy">
                  Host
                </span>
              </div>
              <div className="relative border-b border-border p-2">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                <input
                  value={attendeeSearch}
                  onChange={(e) => setAttendeeSearch(e.target.value)}
                  placeholder="Search by name or role…"
                  className={`${inputClass} pl-9`}
                />
                {attendeeSearch && (
                  <button
                    type="button"
                    onClick={() => setAttendeeSearch('')}
                    aria-label="Clear search"
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted hover:bg-surfaceWarm hover:text-ink"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              {selectedPeople.length > 0 && (
                <div className="flex flex-wrap gap-1.5 border-b border-border bg-surface p-2.5">
                  {selectedPeople.map((u) => (
                    <span
                      key={u.id}
                      className="inline-flex items-center gap-1 rounded-full bg-orange/10 py-0.5 pl-2.5 pr-1 text-xs font-medium text-orange"
                    >
                      {u.name}
                      <button
                        type="button"
                        onClick={() => toggleAttendee(u.id)}
                        aria-label={`Remove ${u.name}`}
                        className="rounded-full p-0.5 hover:bg-orange/15"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div className="max-h-44 space-y-0.5 overflow-y-auto p-2">
                {filtered.length === 0 ? (
                  <p className="px-2 py-4 text-center text-sm text-muted">
                    {users.isPending ? 'Loading…' : 'No people match that search.'}
                  </p>
                ) : (
                  filtered.map((u) => {
                    const checked = selectedSet.has(u.id);
                    return (
                      <label
                        key={u.id}
                        className={`flex cursor-pointer items-center gap-3 rounded-md px-2.5 py-2 transition ${
                          checked ? 'bg-orange/5' : 'hover:bg-surfaceWarm'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleAttendee(u.id)}
                          className="h-4 w-4 shrink-0 rounded border-border accent-orange"
                        />
                        <span
                          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border text-[11px] font-bold shadow-sm ${
                            checked
                              ? 'border-[#C9964A]/20 bg-azure text-white'
                              : 'border-border bg-graphite/10 text-graphite'
                          }`}
                        >
                          {initials(u.name)}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-ink">{u.name}</span>
                          <span className="block truncate text-xs text-muted">{u.designation ?? '—'}</span>
                        </span>
                        {u.org_level_code && (
                          <span
                            className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                              LEVEL_BADGE[u.org_level_code as keyof typeof LEVEL_BADGE] ?? 'bg-graphite/10 text-graphite'
                            }`}
                          >
                            {u.org_level_code}
                          </span>
                        )}
                      </label>
                    );
                  })
                )}
              </div>
            </div>
          </FormSection>

          <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted">Fields marked * are required. Attendees get a notification.</p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={onClose} className={secondaryBtnClass}>
                Cancel
              </button>
              <button
                type="submit"
                disabled={save.isPending || !canSchedule}
                className={`${primaryBtnClass} min-w-[10rem]`}
              >
                {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Schedule meeting
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
