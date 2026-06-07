import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { addDays } from 'date-fns';
import { fetchProjectBoard, fetchCalendarEvents } from '../services/api';

const STALE_TIME = 15 * 60 * 1000; // 15 minutes

/**
 * Prefetches projects and calendar events into the exact query-cache keys that
 * useNewsFeed reads for personalization context:
 *   ['projects']          → ProjectItem[]  (useNewsFeed maps p.name)
 *   ['calendar', 'events'] → CalendarEvent[] (useNewsFeed maps e.summary)
 *
 * These keys are deliberately the ones useNewsFeed reads — do NOT rename them
 * without updating useNewsFeed's getQueryData calls, or the personalization
 * context silently goes empty again.
 *
 * The 2-element ['calendar', 'events'] key is distinct from the calendar page's
 * param-scoped ['calendar', 'events', start, end] (no write collision), but note
 * a calendar sync/update invalidates by prefix and so also marks this entry
 * stale. Since the prefetch is mount-only, the news context then keeps its
 * (retained) stale events until the next shell mount re-warms it — an accepted
 * trade-off: still strictly better than the previously-empty baseline.
 *
 * prefetchQuery is a no-op when data is already fresh within staleTime,
 * so repeated mounts do not trigger redundant network requests.
 */
export default function useNewsContextPrefetch(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const today = new Date();
    const start = today.toISOString().split('T')[0];
    const end = addDays(today, 7).toISOString().split('T')[0];

    queryClient.prefetchQuery({
      queryKey: ['projects'],
      queryFn: async () => (await fetchProjectBoard()).projects,
      staleTime: STALE_TIME,
    });

    queryClient.prefetchQuery({
      queryKey: ['calendar', 'events'],
      queryFn: async () => (await fetchCalendarEvents(start, end)).events,
      staleTime: STALE_TIME,
    });
  }, [queryClient]);
}
