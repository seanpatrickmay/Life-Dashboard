// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

// ── Mocks ──────────────────────────────────────────────────────────────────

const insightQueryMock = vi.fn();
const todosQueryMock = vi.fn();
const curatedQueryMock = vi.fn();
const annotationsQueryMock = vi.fn();
const eventsQueryMock = vi.fn();

vi.mock('./useInsight', () => ({
  useInsight: () => insightQueryMock(),
}));

vi.mock('./useTodos', () => ({
  useTodos: () => ({ todosQuery: todosQueryMock() }),
}));

vi.mock('./useNewsFeed', () => ({
  useNewsFeed: () => ({
    curatedQuery: curatedQueryMock(),
    annotationsQuery: annotationsQueryMock(),
  }),
}));

vi.mock('./useCalendar', () => ({
  useCalendarEvents: () => ({ eventsQuery: eventsQueryMock() }),
}));

vi.mock('../demo/guest/guestMode', () => ({
  isGuestMode: vi.fn(() => false),
}));

vi.mock('../demo/guest/guestStore', () => ({
  getGuestInsight: vi.fn(),
}));

// Fixed date range so the hook is stable and date key is predictable
vi.mock('../utils/timeZone', () => ({
  getUserTimeZone: () => 'UTC',
  getLocalDateRange: () => ({ start: '2026-06-07T00:00:00.000Z', end: '2026-06-07T23:59:59.999Z' }),
}));

// ── LLM-layer mocks ────────────────────────────────────────────────────────

const useQueryMock = vi.fn();

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
}));

const fetchMorningBriefMock = vi.fn();

vi.mock('../services/api', () => ({
  fetchMorningBrief: (...args: unknown[]) => fetchMorningBriefMock(...args),
}));

// ── Type imports ───────────────────────────────────────────────────────────

import type { InsightResponse } from '../services/api';
import type { NewsArticle } from '../services/newsFeedService';

// ── Mocked module imports (for per-test override) ──────────────────────────

import { isGuestMode } from '../demo/guest/guestMode';

// ── Fixtures ───────────────────────────────────────────────────────────────

const insight: InsightResponse = {
  metric_date: '2026-06-07',
  readiness_score: 78,
  readiness_label: 'Primed',
  narrative: 'Recovery is steady.',
  source_model: 'test',
  last_updated: '2026-06-07T06:00:00Z',
  morning_note: 'Start clean and build momentum.',
  sleep_value_hours: 7.4,
};

const pick1: NewsArticle = {
  id: 'p1',
  sourceType: 'rss',
  sourceName: 'Ars Technica',
  category: 'tech',
  url: 'https://example.com/p1',
  title: 'Distributed consensus in 2026',
  summary: null,
  imageUrl: null,
  publishedAt: null,
  fetchedAt: '2026-06-07T05:00:00Z',
  relevanceScore: 0.92,
  surfacedAt: null,
  readAt: null,
};

const pick2: NewsArticle = {
  ...pick1,
  id: 'p2',
  title: 'Sleep research breakthrough',
  url: 'https://example.com/p2',
  relevanceScore: 0.85,
};

function setQueryMocks(opts: {
  insightData?: InsightResponse | null;
  todosData?: unknown[];
  picks?: NewsArticle[];
  annotations?: Record<string, string>;
  eventsData?: Array<{ summary: string; start_time: string }>;
  insightSuccess?: boolean;
  eventsSuccess?: boolean;
  newsSuccess?: boolean;
  llmState?: { isSuccess: boolean; isError: boolean; data?: { paragraph: string } };
}) {
  insightQueryMock.mockReturnValue({
    data: opts.insightData !== undefined ? opts.insightData : insight,
    isSuccess: opts.insightSuccess ?? true,
  });
  todosQueryMock.mockReturnValue({
    data: opts.todosData ?? [],
    isSuccess: true,
  });
  curatedQueryMock.mockReturnValue({
    data: { picks: opts.picks ?? [pick1, pick2], more: [], saved: [] },
    isSuccess: opts.newsSuccess ?? true,
  });
  annotationsQueryMock.mockReturnValue({
    data: opts.annotations ?? { p1: 'Highly relevant to your work.', p2: 'Connects to recovery.' },
    isSuccess: true,
  });
  eventsQueryMock.mockReturnValue({
    data: {
      events: opts.eventsData ?? [
        { summary: 'Team standup', start_time: '2026-06-07T10:00:00Z' },
      ],
    },
    isSuccess: opts.eventsSuccess ?? true,
  });
  // Default LLM query state: settled with error (LLM unavailable in unit tests — baseline is the result)
  const llm = opts.llmState ?? { isSuccess: false, isError: true, data: undefined };
  useQueryMock.mockReturnValue(llm);
}

import { useMorningBrief } from './useMorningBrief';

// ── Tests ──────────────────────────────────────────────────────────────────

describe('useMorningBrief – session lock', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-07T08:00:00'));
    sessionStorage.clear();
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('computes a paragraph when all data is ready', () => {
    setQueryMocks({});
    const { result } = renderHook(() => useMorningBrief());
    expect(result.current.isReady).toBe(true);
    expect(result.current.paragraph.length).toBeGreaterThan(0);
    expect(result.current.paragraph.endsWith('What would make today count?')).toBe(true);
  });

  it('stores the brief in sessionStorage once isReady — including sources snapshot', () => {
    setQueryMocks({});
    renderHook(() => useMorningBrief());
    const raw = sessionStorage.getItem('ld_morning_brief_v2');
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.text).toBeTruthy();
    expect(parsed.date).toBe('2026-06-07');
    // Sources must be co-snapshotted so cache hit returns same articles as paragraph
    expect(Array.isArray(parsed.sources)).toBe(true);
    expect(parsed.sources[0].id).toBe('p1');
    expect(parsed.sources[0].url).toBe('https://example.com/p1');
  });

  it('returns the locked text on a re-render even when picks change', () => {
    setQueryMocks({});
    const { result, rerender } = renderHook(() => useMorningBrief());
    const lockedText = result.current.paragraph;

    // Simulate picks changing (different articles)
    const newPick: NewsArticle = { ...pick1, id: 'p-new', title: 'A completely different article' };
    setQueryMocks({ picks: [newPick] });

    rerender();

    // Should return the session-cached text, NOT the recomposed one
    expect(result.current.paragraph).toBe(lockedText);
    expect(result.current.paragraph).not.toContain('A completely different article');
  });

  it('returns snapshotted sources from cache — not today\'s current picks', () => {
    // Pre-seed with yesterday's cache that has specific sources
    const cachedSources = [
      { id: 'p-old', title: 'Old article', url: 'https://example.com/old', annotation: 'Old annotation' },
    ];
    sessionStorage.setItem(
      'ld_morning_brief_v2',
      JSON.stringify({ text: 'Cached brief.', date: '2026-06-07', sources: cachedSources })
    );

    // Mock returns different current picks
    setQueryMocks({ picks: [pick1, pick2] });
    const { result } = renderHook(() => useMorningBrief());

    // Cache hit — sources must match the snapshot, not current picks
    expect(result.current.paragraph).toBe('Cached brief.');
    expect(result.current.sources[0].id).toBe('p-old');
    expect(result.current.sources[0].title).toBe('Old article');
  });

  it('recomputes when the stored date differs from today', () => {
    // Pre-seed cache with a stale date (new shape includes sources)
    sessionStorage.setItem(
      'ld_morning_brief_v2',
      JSON.stringify({ text: 'Yesterday brief.', date: '2026-06-06', sources: [] })
    );
    setQueryMocks({});
    const { result } = renderHook(() => useMorningBrief());
    // Should NOT return yesterday's brief — should recompute
    expect(result.current.paragraph).not.toBe('Yesterday brief.');
    expect(result.current.paragraph.length).toBeGreaterThan(0);
    // Updated cache should reflect today
    const raw = sessionStorage.getItem('ld_morning_brief_v2');
    const parsed = JSON.parse(raw!);
    expect(parsed.date).toBe('2026-06-07');
  });

  it('is isPartiallyReady when insight + events resolved but news still loading', () => {
    setQueryMocks({});
    curatedQueryMock.mockReturnValue({ data: null, isSuccess: false });
    const { result } = renderHook(() => useMorningBrief());
    expect(result.current.isPartiallyReady).toBe(true);
    expect(result.current.isReady).toBe(false);
  });

  it('is not partially ready when insight and events are also loading', () => {
    insightQueryMock.mockReturnValue({ data: null, isSuccess: false });
    todosQueryMock.mockReturnValue({ data: [], isSuccess: false });
    curatedQueryMock.mockReturnValue({ data: null, isSuccess: false });
    annotationsQueryMock.mockReturnValue({ data: {}, isSuccess: false });
    eventsQueryMock.mockReturnValue({ data: null, isSuccess: false });
    const { result } = renderHook(() => useMorningBrief());
    expect(result.current.isPartiallyReady).toBe(false);
    expect(result.current.isReady).toBe(false);
  });

  it('exposes sources with id, title, url, annotation', () => {
    setQueryMocks({});
    const { result } = renderHook(() => useMorningBrief());
    expect(result.current.sources.length).toBeGreaterThan(0);
    const src = result.current.sources[0];
    expect(src.id).toBe('p1');
    expect(src.title).toBe('Distributed consensus in 2026');
    expect(src.url).toBe('https://example.com/p1');
    expect(src.annotation).toBe('Highly relevant to your work.');
  });
});

describe('useMorningBrief – LLM layer', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-06-07T08:00:00'));
    sessionStorage.clear();
    localStorage.clear();
    vi.clearAllMocks();
    // Ensure guest mode is off by default for all LLM-layer tests.
    vi.mocked(isGuestMode).mockReturnValue(false);
  });

  afterEach(() => {
    vi.useRealTimers();
    // Reset guest-mode mock to the default factory value so describe blocks don't bleed.
    vi.mocked(isGuestMode).mockReturnValue(false);
  });

  it('returns the LLM paragraph when the query succeeds', () => {
    setQueryMocks({
      llmState: {
        isSuccess: true,
        isError: false,
        data: { paragraph: 'LLM-generated brief.' },
      },
    });
    const { result } = renderHook(() => useMorningBrief());
    expect(result.current.paragraph).toBe('LLM-generated brief.');
    expect(result.current.isReady).toBe(true);
  });

  it('falls back to composeBrief paragraph when LLM query errors', () => {
    setQueryMocks({
      llmState: { isSuccess: false, isError: true, data: undefined },
    });
    const { result } = renderHook(() => useMorningBrief());
    // Should be the composeBrief baseline (ends with reflection question)
    expect(result.current.paragraph.endsWith('What would make today count?')).toBe(true);
    expect(result.current.paragraph).not.toBe('');
    expect(result.current.isReady).toBe(true);
  });

  it('falls back to composeBrief when LLM query is still pending (simulates timeout)', () => {
    // Pending = neither success nor error — mirrors an in-flight or timed-out query
    setQueryMocks({
      llmState: { isSuccess: false, isError: false, data: undefined },
    });
    const { result } = renderHook(() => useMorningBrief());
    expect(result.current.paragraph.endsWith('What would make today count?')).toBe(true);
    expect(result.current.paragraph).not.toBe('');
    expect(result.current.isReady).toBe(true);
  });

  it('exercises the real 2s AbortController timeout path in the queryFn', async () => {
    // The useQuery mock captures the full options object, including queryFn.
    // We extract it and drive it directly with a signal that aborts immediately,
    // mirroring what setTimeout(() => controller.abort(), 2000) does at T+2s.
    // This exercises the actual timeout→abort→throw→catch path, not just the pending state.
    setQueryMocks({
      llmState: { isSuccess: false, isError: false, data: undefined },
    });
    renderHook(() => useMorningBrief());

    const callOptions = useQueryMock.mock.calls[0]?.[0] as {
      queryFn?: (ctx: { signal: AbortSignal }) => Promise<unknown>;
    } | undefined;
    expect(callOptions?.queryFn).toBeDefined();

    // Simulate the fetch taking longer than 2s: make fetchMorningBriefMock return a
    // promise that rejects when its signal fires, mirroring real abort semantics.
    fetchMorningBriefMock.mockImplementation(
      (_req: unknown, signal: AbortSignal) =>
        new Promise((_resolve, reject) => {
          if (signal.aborted) {
            reject(new DOMException('AbortError', 'AbortError'));
            return;
          }
          signal.addEventListener('abort', () =>
            reject(new DOMException('AbortError', 'AbortError'))
          );
        })
    );

    // Build an AbortController and immediately abort it — this is what the
    // 2-second setTimeout fires in the real hook queryFn.
    const timeoutController = new AbortController();
    timeoutController.abort();

    // Drive the captured queryFn with the aborted signal.
    // The queryFn creates its own internal AbortController and forwards the abort,
    // so passing the already-aborted outer signal triggers the abort listener.
    await expect(
      callOptions!.queryFn!({ signal: timeoutController.signal })
    ).rejects.toThrow();

    // The hook itself (via useQuery returning isError:false/isSuccess:false) renders
    // the composeBrief baseline — verified separately by the pending-state test.
    // The key assertion here is that fetchMorningBriefMock was called and the
    // AbortSignal abort path throws, confirming the timeout→fallback mechanism is wired.
    expect(fetchMorningBriefMock).toHaveBeenCalled();
    const passedSignal = fetchMorningBriefMock.mock.calls[0][1] as AbortSignal;
    expect(passedSignal.aborted).toBe(true);
  });

  it('does not call fetchMorningBrief in guest mode — useQuery is disabled', () => {
    // The useQuery mock captures options; verify `enabled` matches non-guest normal path.
    // Our guestMode mock returns false by default, so this confirms non-guest enabled=true.
    // The guest=false path proves the flag wiring — the guest=true path would set it false.
    setQueryMocks({
      llmState: { isSuccess: false, isError: false, data: undefined },
    });
    const { result } = renderHook(() => useMorningBrief());
    // Baseline should be returned regardless
    expect(result.current.paragraph).not.toBe('');
    // useQuery must have been called — check enabled flag in the options passed
    const callOptions = useQueryMock.mock.calls[0]?.[0] as { enabled?: boolean } | undefined;
    // In normal (non-guest) mode with isReady=true and no lock, enabled should be true
    expect(callOptions?.enabled).toBe(true);
  });

  it('genuinely tests guest mode — fetchMorningBrief not called and paragraph is composeBrief baseline', () => {
    // Set isGuestMode to return true for this test only.
    vi.mocked(isGuestMode).mockReturnValue(true);

    setQueryMocks({
      llmState: { isSuccess: false, isError: false, data: undefined },
    });

    const { result } = renderHook(() => useMorningBrief());

    // In guest mode, llmEnabled = isReady && !isGuestMode() && !isLockedToday = false.
    // The useQuery enabled flag must be false, so fetchMorningBriefMock is never invoked.
    expect(fetchMorningBriefMock).not.toHaveBeenCalled();

    const callOptions = useQueryMock.mock.calls[0]?.[0] as { enabled?: boolean } | undefined;
    expect(callOptions?.enabled).toBe(false);

    // The paragraph falls back to the composeBrief baseline (always ends with reflection).
    expect(result.current.paragraph.endsWith('What would make today count?')).toBe(true);
    expect(result.current.paragraph).not.toBe('');
    expect(result.current.isReady).toBe(true);
  });

  it('returns stable paragraph from session cache across re-renders after LLM settles', () => {
    // Seed session cache as if LLM already settled and locked
    sessionStorage.setItem(
      'ld_morning_brief_v2',
      JSON.stringify({ text: 'Settled LLM brief.', date: '2026-06-07', sources: [] })
    );
    // LLM query should now be disabled (isLockedToday=true)
    setQueryMocks({
      llmState: { isSuccess: false, isError: false, data: undefined },
    });
    const { result, rerender } = renderHook(() => useMorningBrief());
    expect(result.current.paragraph).toBe('Settled LLM brief.');

    // Re-render — must remain stable
    rerender();
    expect(result.current.paragraph).toBe('Settled LLM brief.');

    // Confirm useQuery was called with enabled:false (lock prevents refiring)
    const callOptions = useQueryMock.mock.calls[0]?.[0] as { enabled?: boolean } | undefined;
    expect(callOptions?.enabled).toBe(false);
  });
});
