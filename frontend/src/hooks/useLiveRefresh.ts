import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

/**
 * Polls the given query keys in the background while the page is mounted and
 * the tab is visible, so approval decisions / status changes surface without
 * a manual refresh. Pauses automatically when the tab is hidden and resumes
 * (with an instant tick) when it becomes visible again.
 *
 * Returns the millisecond timestamp of the last completed poll, which can be
 * fed to <LiveIndicator />.
 */
export function useLiveRefresh(
  queryKeys: (readonly unknown[])[],
  intervalMs = 30_000,
): number | null {
  const queryClient = useQueryClient();
  const [lastTickAt, setLastTickAt] = useState<number | null>(null);
  const keysRef = useRef(queryKeys);
  keysRef.current = queryKeys;

  useEffect(() => {
    let inFlight = false;

    const tick = async () => {
      if (document.visibilityState !== 'visible' || inFlight) return;
      inFlight = true;
      try {
        await Promise.all(
          keysRef.current.map((key) =>
            queryClient.refetchQueries({ queryKey: key, type: 'active' }),
          ),
        );
        setLastTickAt(Date.now());
      } catch {
        // Network hiccups are surfaced by each query's own error state.
      } finally {
        inFlight = false;
      }
    };

    const id = window.setInterval(tick, intervalMs);
    const onVisible = () => {
      if (document.visibilityState === 'visible') void tick();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [intervalMs, queryClient]);

  return lastTickAt;
}