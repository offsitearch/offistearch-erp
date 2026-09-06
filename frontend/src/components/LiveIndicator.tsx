import { RefreshCw } from 'lucide-react';

/**
 * Small floating pill shown on pages that auto-refresh — tells the user the
 * page is live and approvals / changes will appear on their own.
 */
export function LiveIndicator({ lastTickAt }: { lastTickAt: number | null }) {
  const label = lastTickAt
    ? `updated ${new Date(lastTickAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    : 'refreshing…';

  return (
    <span
      title="This page updates automatically — approvals and changes appear live, usually within a minute."
      className="inline-flex items-center gap-1.5 rounded-full border border-info/20 bg-infoSoft px-2 py-0.5 text-[11px] font-medium text-info"
    >
      <RefreshCw className={`h-3 w-3 ${lastTickAt ? '' : 'animate-spin'}`} />
      Live · {label}
    </span>
  );
}