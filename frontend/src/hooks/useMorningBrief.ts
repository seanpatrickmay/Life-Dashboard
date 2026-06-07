import { useMemo } from 'react';
import { useInsight } from './useInsight';
import { useTodos } from './useTodos';
import { useNewsFeed } from './useNewsFeed';
import { useCalendarEvents } from './useCalendar';
import { getLocalDateRange } from '../utils/timeZone';
import { composeBrief } from '../utils/composeBrief';
import { isGuestMode } from '../demo/guest/guestMode';
import { getGuestInsight } from '../demo/guest/guestStore';
import type { NewsArticle } from '../services/newsFeedService';

const SESSION_KEY = 'ld_morning_brief_v2';

export interface BriefSource {
  id: string;
  title: string;
  url: string;
  annotation: string | null;
}

interface CachedBrief {
  text: string;
  date: string;
  sources: BriefSource[];
}

export interface MorningBriefResult {
  paragraph: string;
  sources: BriefSource[];
  isReady: boolean;
  isPartiallyReady: boolean;
}

function getLocalDateKey(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function loadSessionBrief(): CachedBrief | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as CachedBrief;
  } catch {
    return null;
  }
}

function saveSessionBrief(text: string, date: string, sources: BriefSource[]): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ text, date, sources }));
  } catch {
    // sessionStorage unavailable (SSR or private browsing edge case)
  }
}

export function useMorningBrief(): MorningBriefResult {
  const { start, end } = useMemo(() => getLocalDateRange(), []);

  const insightQuery = useInsight();
  const { todosQuery } = useTodos();
  const { curatedQuery, annotationsQuery } = useNewsFeed();
  const { eventsQuery } = useCalendarEvents(start, end);

  return useMemo(() => {
    const today = getLocalDateKey();

    // Determine insight source (guest or real)
    const rawInsight = isGuestMode()
      ? getGuestInsight()
      : (insightQuery.data ?? null);

    const insightReady = isGuestMode() ? true : insightQuery.isSuccess;
    const eventsReady = eventsQuery.isSuccess;
    const newsReady = curatedQuery.isSuccess;

    // Partial = readiness + events resolved (fast path ~1s)
    const isPartiallyReady = insightReady && eventsReady;
    // Full = all three resolved
    const isReady = isPartiallyReady && newsReady;

    const events = (eventsQuery.data?.events ?? []).map(e => ({
      summary: e.summary ?? null,
      start_time: e.start_time ?? null,
    }));

    const todos = todosQuery.data ?? [];
    const overdueTasks = todos
      .filter(t => !t.completed && t.is_overdue)
      .map(t => t.text);

    const picks: NewsArticle[] = curatedQuery.data?.picks?.slice(0, 2) ?? [];
    const annotations: Record<string, string> = annotationsQuery.data ?? {};

    // Check session cache — return stable text AND the snapshot sources from the same compose run
    const cached = loadSessionBrief();
    if (cached && cached.date === today && isReady) {
      return {
        paragraph: cached.text,
        sources: cached.sources,
        isReady: true,
        isPartiallyReady: true,
      };
    }

    if (!insightReady && !isPartiallyReady) {
      return { paragraph: '', sources: [], isReady: false, isPartiallyReady: false };
    }

    const paragraph = composeBrief({
      insight: rawInsight,
      events,
      overdueTasks,
      picks,
      annotations,
    });

    const sources: BriefSource[] = picks.slice(0, 2).map(p => ({
      id: p.id,
      title: p.title,
      url: p.url,
      annotation: annotations[p.id] ?? null,
    }));

    // Persist to session once fully ready — snapshot both text and sources together
    if (isReady && paragraph) {
      saveSessionBrief(paragraph, today, sources);
    }

    return { paragraph, sources, isReady, isPartiallyReady };
  }, [
    insightQuery.data,
    insightQuery.isSuccess,
    eventsQuery.data,
    eventsQuery.isSuccess,
    todosQuery.data,
    curatedQuery.data,
    curatedQuery.isSuccess,
    annotationsQuery.data,
    start,
    end,
  ]);
}
