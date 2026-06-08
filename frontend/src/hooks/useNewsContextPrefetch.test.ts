// @vitest-environment jsdom
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ─────────────────────────────────────────────────────────────────

const fetchProjectBoardMock = vi.fn();
const fetchCalendarEventsMock = vi.fn();

vi.mock('../services/api', () => ({
  fetchProjectBoard: (...args: unknown[]) => fetchProjectBoardMock(...args),
  fetchCalendarEvents: (...args: unknown[]) => fetchCalendarEventsMock(...args),
}));

// ── Helpers ───────────────────────────────────────────────────────────────

function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

// ── Tests ─────────────────────────────────────────────────────────────────

describe('useNewsContextPrefetch', () => {
  let queryClient: QueryClient;

  beforeEach(async () => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          // disable staleTime so prefetch always fires in tests
          staleTime: 0,
        },
      },
    });

    fetchProjectBoardMock.mockResolvedValue({
      projects: [
        { id: 1, name: 'Life Dashboard', archived: false, sort_order: 0, notes: null, open_count: 2, completed_count: 5, created_at: '', updated_at: '' },
        { id: 2, name: 'Mandarin Learning', archived: false, sort_order: 1, notes: null, open_count: 1, completed_count: 0, created_at: '', updated_at: '' },
      ],
      todos: [],
      suggestions: [],
    });

    fetchCalendarEventsMock.mockResolvedValue({
      events: [
        { id: 1, calendar_google_id: 'cal1', calendar_summary: 'Personal', calendar_primary: true, calendar_is_life_dashboard: false, google_event_id: 'evt1', summary: 'Team Standup', start_time: '2026-06-07T09:00:00Z', end_time: '2026-06-07T09:30:00Z', is_all_day: false },
        { id: 2, calendar_google_id: 'cal1', calendar_summary: 'Personal', calendar_primary: true, calendar_is_life_dashboard: false, google_event_id: 'evt2', summary: 'Doctor Appointment', start_time: '2026-06-09T14:00:00Z', end_time: '2026-06-09T15:00:00Z', is_all_day: false },
      ],
    });
  });

  it('calls prefetchQuery for news-context projects key on mount', async () => {
    const prefetchSpy = vi.spyOn(queryClient, 'prefetchQuery');

    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    const projectsCall = prefetchSpy.mock.calls.find(
      (call) => JSON.stringify((call[0] as { queryKey: unknown }).queryKey) === JSON.stringify(['news-context', 'projects'])
    );
    expect(projectsCall).toBeDefined();
  });

  it('calls prefetchQuery for news-context calendar key on mount', async () => {
    const prefetchSpy = vi.spyOn(queryClient, 'prefetchQuery');

    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    const calendarCall = prefetchSpy.mock.calls.find(
      (call) => JSON.stringify((call[0] as { queryKey: unknown }).queryKey) === JSON.stringify(['news-context', 'calendar'])
    );
    expect(calendarCall).toBeDefined();
  });

  it('populates cache with ProjectItem[] at key [news-context, projects] — items have .name', async () => {
    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    // Wait for prefetch to resolve
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const cached = queryClient.getQueryData<{ name: string }[]>(['news-context', 'projects']);
    expect(Array.isArray(cached)).toBe(true);
    expect(cached![0]).toHaveProperty('name');
    expect(cached![0].name).toBe('Life Dashboard');
  });

  it('populates cache with CalendarEvent[] at key [news-context, calendar] — items have .summary', async () => {
    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const cached = queryClient.getQueryData<{ summary?: string | null }[]>(['news-context', 'calendar']);
    expect(Array.isArray(cached)).toBe(true);
    expect(cached![0]).toHaveProperty('summary');
    expect(cached![0].summary).toBe('Team Standup');
  });

  it('does not clobber calendar page cache at param-scoped key [calendar, events, start, end]', async () => {
    const start = '2026-06-07';
    const end = '2026-06-14';
    const pageCacheData = [{ id: 99, summary: 'Page-level event' }];

    // Pre-populate the calendar page's scoped cache entry
    queryClient.setQueryData(['calendar', 'events', start, end], pageCacheData);

    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // The param-scoped cache entry must still be the original value
    const scopedCache = queryClient.getQueryData(['calendar', 'events', start, end]);
    expect(scopedCache).toEqual(pageCacheData);
  });

  it('uses staleTime of 15 minutes so prefetch is a no-op when data is fresh', async () => {
    const prefetchSpy = vi.spyOn(queryClient, 'prefetchQuery');

    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const projectsCall = prefetchSpy.mock.calls.find(
      (call) => JSON.stringify((call[0] as { queryKey: unknown; staleTime?: number }).queryKey) === JSON.stringify(['news-context', 'projects'])
    );
    const staleTime = (projectsCall?.[0] as { staleTime?: number })?.staleTime;
    expect(staleTime).toBe(15 * 60 * 1000);
  });

  it('regression: calendar invalidation does NOT evict [news-context, calendar] from cache', async () => {
    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // Confirm news-context calendar is populated
    const beforeInvalidation = queryClient.getQueryData<{ summary?: string | null }[]>(['news-context', 'calendar']);
    expect(Array.isArray(beforeInvalidation)).toBe(true);
    expect(beforeInvalidation!.length).toBeGreaterThan(0);

    // Simulate the exact invalidation useCalendar's sync/update mutations fire
    await act(async () => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events'] });
    });

    // The news-context entry must still be present and not stale-evicted
    // (invalidation by prefix ['calendar','events'] cannot reach ['news-context','calendar'])
    const afterInvalidation = queryClient.getQueryData<{ summary?: string | null }[]>(['news-context', 'calendar']);
    expect(Array.isArray(afterInvalidation)).toBe(true);
    expect(afterInvalidation!.length).toBeGreaterThan(0);
    expect(afterInvalidation![0].summary).toBe('Team Standup');
  });

  it('regression: projects invalidation does NOT evict [news-context, projects] from cache', async () => {
    const { default: useNewsContextPrefetch } = await import('./useNewsContextPrefetch');

    await act(async () => {
      renderHook(() => useNewsContextPrefetch(), { wrapper: makeWrapper(queryClient) });
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    const beforeInvalidation = queryClient.getQueryData<{ name: string }[]>(['news-context', 'projects']);
    expect(Array.isArray(beforeInvalidation)).toBe(true);

    // Simulate invalidation by ['projects'] prefix (as any board mutation would do)
    await act(async () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    });

    // ['news-context','projects'] must be untouched
    const afterInvalidation = queryClient.getQueryData<{ name: string }[]>(['news-context', 'projects']);
    expect(Array.isArray(afterInvalidation)).toBe(true);
    expect(afterInvalidation!.length).toBeGreaterThan(0);
    expect(afterInvalidation![0].name).toBe('Life Dashboard');
  });
});
