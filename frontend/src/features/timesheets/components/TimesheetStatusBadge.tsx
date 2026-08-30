import { timesheetStatusMeta } from '../../../lib/constants';
import type { TimesheetStatus } from '../../../lib/types';

export function TimesheetStatusBadge({
  status,
  compact = false,
}: {
  status: TimesheetStatus;
  compact?: boolean;
}) {
  const meta = timesheetStatusMeta(status);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-semibold ${meta.badge} ${
        compact ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs'
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}
