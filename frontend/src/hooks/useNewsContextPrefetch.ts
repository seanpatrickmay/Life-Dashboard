import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { addDays } from 'date-fns';
import { fetchProjectBoard, fetchCalendarEvents } from '../services/api';

const STALE_TIME = 15 * 60 * 1000; // 15 minutes

/**
 * Prefetches projects and calendar events into dedicated news-personalization
 * context keys that no app mutation will ever invalidate:
 *   ['news-context', 'projects']  → ProjectItem[]  (useNewsFeed maps p.name)
 *   ['news-context', 'calendar']  → CalendarEvent[] (useNewsFeed maps e.summary)
 *
 * These keys are intentionally isolated from the calendar page's own cache
 * hierarchy (['calendar', 'events', start, end]) and the board's hierarchy
 * (['projects', 'board']). Because React Query prefix-matching cannot reach
 * ['news-context', …] from invalidations on ['calendar', 'events'] or
 * ['projects'], a calendar sync or project update will never evict this
 * personalization snapshot — the news feed always has valid context data.
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
      queryKey: ['news-context', 'projects'],
      queryFn: async () => (await fetchProjectBoard()).projects,
      staleTime: STALE_TIME,
    });

    queryClient.prefetchQuery({
      queryKey: ['news-context', 'calendar'],
      queryFn: async () => (await fetchCalendarEvents(start, end)).events,
      staleTime: STALE_TIME,
    });
  }, [queryClient]);
}
