// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest';
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
  isGuestMode: () => false,
}));

vi.mock('../demo/guest/guestStore', () => ({
  getGuestInsight: vi.fn(),
}));

// Fixed date range so the hook is stable and date key is predictable
vi.mock('../utils/timeZone', () => ({
  getUserTimeZone: () => 'UTC',
  getLocalDateRange: () => ({ start: '2026-06-07T00:00:00.000Z', end: '2026-06-07T23:59:59.999Z' }),
}));

// ── Type imports ───────────────────────────────────────────────────────────

import type { InsightResponse } from '../services/api';
import type { NewsArticle } from '../services/newsFeedService';

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
}

import { useMorningBrief } from './useMorningBrief';

// ── Tests ──────────────────────────────────────────────────────────────────

describe('useMorningBrief – session lock', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('computes a paragraph when all data is ready', () => {
    setQueryMocks({});
    const { result } = renderHook(() => useMorningBrief());
    expect(result.current.isReady).toBe(true);
    expect(result.current.paragraph.length).toBeGreaterThan(0);
    expect(result.current.paragraph.endsWith('What would make today count?')).toBe(true);
  });

  it('stores the brief in sessionStorage once isReady', () => {
    setQueryMocks({});
    renderHook(() => useMorningBrief());
    const raw = sessionStorage.getItem('ld_morning_brief_v1');
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.text).toBeTruthy();
    expect(parsed.date).toBe('2026-06-07');
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

  it('recomputes when the stored date differs from today', () => {
    // Pre-seed cache with a stale date
    sessionStorage.setItem(
      'ld_morning_brief_v1',
      JSON.stringify({ text: 'Yesterday brief.', date: '2026-06-06' })
    );
    setQueryMocks({});
    const { result } = renderHook(() => useMorningBrief());
    // Should NOT return yesterday's brief — should recompute
    expect(result.current.paragraph).not.toBe('Yesterday brief.');
    expect(result.current.paragraph.length).toBeGreaterThan(0);
    // Updated cache should reflect today
    const raw = sessionStorage.getItem('ld_morning_brief_v1');
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
