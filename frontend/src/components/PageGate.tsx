import type { ReactNode } from 'react';
import { LogoLoader } from './LogoLoader';

type QueryLike = {
  isPending: boolean;
  data?: unknown;
};

/**
 * Shows the branded LogoLoader until every gated query has data ready, then
 * renders children. Because React Query keeps a warm in-memory cache, a revisit
 * with fresh data renders instantly (no loader); a genuinely cold/slow fetch
 * keeps the loader on screen until data lands — no skeleton flash between.
 */
export function PageGate({
  queries,
  children,
}: {
  queries: QueryLike | QueryLike[];
  children: ReactNode;
}) {
  const list = Array.isArray(queries) ? queries : [queries];

  const waiting = list.some(
    (q) => q.isPending && (q.data === undefined || q.data === null),
  );

  return waiting ? <LogoLoader /> : <>{children}</>;
}
