import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useInsight } from './useInsight';
import { useTodos } from './useTodos';
import { useNewsFeed } from './useNewsFeed';
import { useCalendarEvents } from './useCalendar';
import { getLocalDateRange } from '../utils/timeZone';
import { composeBrief } from '../utils/composeBrief';
import { isGuestMode } from '../demo/guest/guestMode';
import { getGuestInsight } from '../demo/guest/guestStore';
import { fetchMorningBrief, type MorningBriefRequest } from '../services/api';
import type { NewsArticle } from '../services/newsFeedService';

const SESSION_KEY = 'ld_morning_brief_v2';
const LLM_TIMEOUT_MS = 2000;

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
  const today = getLocalDateKey();

  const insightQuery = useInsight();
  const { todosQuery } = useTodos();
  const { curatedQuery, annotationsQuery } = useNewsFeed();
  const { eventsQuery } = useCalendarEvents(start, end);

  // ── Derived readiness flags ────────────────────────────────────────────────
  const rawInsight = isGuestMode()
    ? getGuestInsight()
    : (insightQuery.data ?? null);

  const insightReady = isGuestMode() ? true : insightQuery.isSuccess;
  const eventsReady = eventsQuery.isSuccess;
  const newsReady = curatedQuery.isSuccess;

  const isPartiallyReady = insightReady && eventsReady;
  const isReady = isPartiallyReady && newsReady;

  // ── Session cache check ────────────────────────────────────────────────────
  const cached = loadSessionBrief();
  const isLockedToday = !!(cached && cached.date === today && isReady);

  // ── Shared input signals ───────────────────────────────────────────────────
  const events = (eventsQuery.data?.events ?? []).map(e => ({
    summary: e.summary ?? null,
    start_time: e.start_time ?? null,
  }));

  const todos = todosQuery.data ?? [];
  const overdueTasks = todos.filter(t => !t.completed && t.is_overdue).map(t => t.text);

  const picks: NewsArticle[] = curatedQuery.data?.picks?.slice(0, 2) ?? [];
  const annotations: Record<string, string> = annotationsQuery.data ?? {};

  // ── Sync baseline (immediate, always available) ────────────────────────────
  const baselineParagraph = useMemo(() => {
    if (!insightReady && !isPartiallyReady) return '';
    return composeBrief({ insight: rawInsight, events, overdueTasks, picks, annotations });
  }, [rawInsight, insightReady, isPartiallyReady, events, overdueTasks, picks, annotations]);

  const sources: BriefSource[] = picks.slice(0, 2).map(p => ({
    id: p.id,
    title: p.title,
    url: p.url,
    annotation: annotations[p.id] ?? null,
  }));

  // ── LLM request shape ─────────────────────────────────────────────────────
  const llmRequest: MorningBriefRequest = {
    readiness: rawInsight ? {
      score: rawInsight.readiness_score ?? null,
      label: rawInsight.readiness_label ?? null,
      sleep_hours: rawInsight.sleep_value_hours ?? null,
      hrv_ms: rawInsight.hrv_value_ms ?? null,
      narrative: rawInsight.morning_note ?? rawInsight.greeting ?? rawInsight.narrative ?? null,
    } : null,
    events,
    overdue_tasks: overdueTasks,
    reads: picks.map(p => ({ title: p.title, annotation: annotations[p.id] ?? null })),
  };

  const llmEnabled = isReady && !isGuestMode() && !isLockedToday;

  // ── LLM query: upgrades baseline within ≤2s; errors/timeouts fall back ─────
  const llmQuery = useQuery({
    queryKey: ['morning-brief-llm', today],
    queryFn: async ({ signal: qSignal }) => {
      const timeoutController = new AbortController();
      const timeoutId = setTimeout(() => timeoutController.abort(), LLM_TIMEOUT_MS);
      qSignal?.addEventListener('abort', () => timeoutController.abort());

      try {
        return await fetchMorningBrief(llmRequest, timeoutController.signal);
      } finally {
        clearTimeout(timeoutId);
      }
    },
    enabled: llmEnabled,
    retry: false,
    staleTime: Infinity,
    gcTime: 24 * 60 * 60 * 1000,
  });

  // ── Final paragraph: LLM upgrades baseline; error/timeout falls back ───────
  const finalParagraph = (llmQuery.isSuccess && llmQuery.data?.paragraph)
    ? llmQuery.data.paragraph
    : baselineParagraph;

  // ── Lock-on-settle: write synchronously when the final value is stable ─────
  // Lock when: fully ready AND (LLM settled OR LLM was never enabled)
  const llmSettled = !llmEnabled || llmQuery.isSuccess || llmQuery.isError;
  if (isReady && finalParagraph && llmSettled && !isLockedToday) {
    saveSessionBrief(finalParagraph, today, sources);
  }

  // ── Return: cached text if locked, else live final ─────────────────────────
  if (isLockedToday && cached) {
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

  return { paragraph: finalParagraph, sources, isReady, isPartiallyReady };
}
