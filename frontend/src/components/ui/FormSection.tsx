import type { LucideIcon } from 'lucide-react';

/**
 * Section header + body used inside form modals (e.g. Schedule Meeting,
 * Log Site Visit). Gives a modal a visual hierarchy: iconed eyebrow label
 * followed by the field group.
 */
export default function FormSection({
  icon: Icon,
  title,
  hint,
  children,
}: {
  icon: LucideIcon;
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-2.5 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-navy/10 text-navy">
          <Icon className="h-3.5 w-3.5" />
        </span>
        <span className="text-xs font-semibold uppercase tracking-wider text-ink">{title}</span>
        {hint && <span className="text-xs font-normal normal-case tracking-normal text-muted">{hint}</span>}
      </div>
      {children}
    </section>
  );
}