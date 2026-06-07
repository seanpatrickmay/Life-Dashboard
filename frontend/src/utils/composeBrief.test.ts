import { describe, it, expect } from 'vitest';
import { composeBrief, REFLECTION, type ComposeBriefInputs } from './composeBrief';
import type { InsightResponse } from '../services/api';
import type { NewsArticle } from '../services/newsFeedService';

const baseInsight: InsightResponse = {
  metric_date: '2026-06-07',
  readiness_score: 78,
  readiness_label: 'Primed',
  narrative: 'Recovery is steady.',
  source_model: 'test',
  last_updated: new Date().toISOString(),
  morning_note: 'Fuel early and choose low-friction wins.',
  sleep_value_hours: 7.5,
  hrv_value_ms: 52,
};

const basePick: NewsArticle = {
  id: 'art-1',
  sourceType: 'rss',
  sourceName: 'Ars Technica',
  category: 'tech',
  url: 'https://example.com/1',
  title: 'The future of distributed systems',
  summary: 'An overview of modern distributed architectures.',
  imageUrl: null,
  publishedAt: null,
  fetchedAt: new Date().toISOString(),
  relevanceScore: 0.9,
  surfacedAt: null,
  readAt: null,
};

const secondPick: NewsArticle = {
  ...basePick,
  id: 'art-2',
  title: 'Sleep and cognitive load',
  url: 'https://example.com/2',
};

const baseEvents = [
  { summary: 'Team standup', start_time: new Date().toISOString() },
  { summary: 'Deep work block', start_time: new Date().toISOString() },
];

const baseInputs: ComposeBriefInputs = {
  insight: baseInsight,
  events: baseEvents,
  overdueTasks: ['Finish report'],
  picks: [basePick, secondPick],
  annotations: {
    'art-1': 'Directly relevant to your current projects.',
    'art-2': 'Connects to your sleep patterns.',
  },
};

// ── Reflection always present ──────────────────────────────────────────────

describe('composeBrief – reflection hook', () => {
  it('always ends with the reflection question', () => {
    const result = composeBrief(baseInputs);
    expect(result.trim().endsWith(REFLECTION)).toBe(true);
  });

  it('ends with reflection even when all optional data is missing', () => {
    const result = composeBrief({ insight: null, events: [], overdueTasks: [], picks: [], annotations: {} });
    expect(result.trim()).toBe(REFLECTION);
  });
});

// ── Full data – synthesis present ─────────────────────────────────────────

describe('composeBrief – full data', () => {
  it('includes morning_note body text', () => {
    const result = composeBrief(baseInputs);
    expect(result).toContain('Fuel early');
  });

  it('includes sleep hours', () => {
    const result = composeBrief(baseInputs);
    expect(result).toContain('7.5h');
  });

  it('includes readiness score and label', () => {
    const result = composeBrief(baseInputs);
    expect(result).toContain('78');
    expect(result).toContain('Primed');
  });

  it('includes schedule events', () => {
    const result = composeBrief(baseInputs);
    expect(result).toContain('Team standup');
    expect(result).toContain('Deep work block');
  });

  it('includes overdue task', () => {
    const result = composeBrief(baseInputs);
    expect(result).toContain('Finish report');
  });

  it('includes second article title', () => {
    const result = composeBrief(baseInputs);
    expect(result).toContain('Sleep and cognitive load');
  });
});

// ── Synthesis: good readiness + sleep + focus event ───────────────────────

describe('composeBrief – synthesis (good readiness + sleep + focus event)', () => {
  it('weaves sleep hours and focus event into the synthesis sentence with the article title', () => {
    // baseInputs has sleep_value_hours=7.5 and a "Deep work block" event
    const result = composeBrief(baseInputs);

    // Must name the top article
    expect(result).toContain('The future of distributed systems');

    // Must reference sleep hours (a concrete non-readiness signal)
    expect(result).toContain('7.5h sleep');

    // Must reference the focus event (a second non-readiness signal)
    expect(result).toContain('Deep work block');

    // The synthesis sentence must be one coherent sentence, not two bare values
    const barePattern = /\d+\/100\.\s+"The future/;
    expect(barePattern.test(result)).toBe(false);
  });

  it('includes annotation text in the synthesis phrase', () => {
    const result = composeBrief(baseInputs);
    expect(result).toContain('relevant to your current projects');
  });
});

// ── Synthesis: low readiness + overdue task ────────────────────────────────

describe('composeBrief – synthesis (low readiness + overdue task)', () => {
  it('names the overdue task alongside the article title in a recovery framing', () => {
    const lowInsight: InsightResponse = {
      ...baseInsight,
      readiness_score: 42,
      readiness_label: 'Strained',
      morning_note: 'Take it easy today.',
      sleep_value_hours: null,
    };
    const result = composeBrief({
      ...baseInputs,
      insight: lowInsight,
      events: [], // no events so task is the only day-signal
    });

    // Must name the article
    expect(result).toContain('The future of distributed systems');

    // Must reference the overdue task by name — proves cross-domain combination
    expect(result).toContain('Finish report');

    // Should frame this as a recovery / lighter day
    expect(
      result.includes('Recovery day') ||
      result.includes('recovery') ||
      result.includes('lighter') ||
      result.includes('slower')
    ).toBe(true);
  });
});

// ── Synthesis: moderate + busy calendar (no focus event) ──────────────────

describe('composeBrief – synthesis (moderate readiness + busy calendar)', () => {
  it('mentions event count as a concrete signal when no focus/review event exists', () => {
    const moderateInsight: InsightResponse = {
      ...baseInsight,
      readiness_score: 62,
      readiness_label: 'Fair',
      sleep_value_hours: null,
    };
    // Four generic events — none match the focus-event regex
    const busyEvents = [
      { summary: 'Team standup', start_time: null },
      { summary: 'Lunch', start_time: null },
      { summary: '1:1 with manager', start_time: null },
      { summary: 'Sprint retrospective demo', start_time: null },
    ];
    const result = composeBrief({
      ...baseInputs,
      insight: moderateInsight,
      events: busyEvents,
      overdueTasks: [],
    });

    // Must name the article
    expect(result).toContain('The future of distributed systems');

    // Must reference the event count — concrete day-signal, not tier-switch alone
    expect(result).toContain('4 things on the calendar');
  });

  it('names a focus/review event rather than count when one is present', () => {
    const moderateInsight: InsightResponse = {
      ...baseInsight,
      readiness_score: 62,
      readiness_label: 'Fair',
      sleep_value_hours: null,
    };
    const result = composeBrief({
      ...baseInputs,
      insight: moderateInsight,
      events: [{ summary: 'Deep work block', start_time: null }],
      overdueTasks: [],
    });

    // Must name the article
    expect(result).toContain('The future of distributed systems');

    // Must reference the focus event by name — concrete signal
    expect(result).toContain('Deep work block');
  });
});

// ── Synthesis: signals absent — graceful fallback ─────────────────────────

describe('composeBrief – synthesis (no extra signals)', () => {
  it('still produces a sentence with the article title when sleep/events/tasks all absent', () => {
    const result = composeBrief({
      ...baseInputs,
      insight: { ...baseInsight, sleep_value_hours: null },
      events: [],
      overdueTasks: [],
    });

    expect(result).toContain('The future of distributed systems');
    // Must still have a coherent bridging phrase rather than bare title
    expect(
      result.includes('dig into') ||
      result.includes('worth a look') ||
      result.includes('stands out') ||
      result.includes('standout read') ||
      result.includes('fits a') ||
      result.includes('relevant to') ||
      result.includes('strongest signal') ||
      result.includes('strongest read')
    ).toBe(true);
  });
});

// ── Missing data – graceful omission ──────────────────────────────────────

describe('composeBrief – missing insight', () => {
  it('omits body segment but still includes events and reflection', () => {
    const result = composeBrief({
      insight: null,
      events: baseEvents,
      overdueTasks: [],
      picks: [],
      annotations: {},
    });
    expect(result).toContain('Team standup');
    expect(result.trim().endsWith(REFLECTION)).toBe(true);
    // No readiness data
    expect(result).not.toContain('Readiness');
  });
});

describe('composeBrief – no events', () => {
  it('omits schedule segment', () => {
    const result = composeBrief({ ...baseInputs, events: [] });
    expect(result).not.toContain('On the schedule');
  });
});

describe('composeBrief – no overdue todos', () => {
  it('omits tasks segment', () => {
    const result = composeBrief({ ...baseInputs, overdueTasks: [] });
    expect(result).not.toContain('Overdue');
  });
});

describe('composeBrief – no picks', () => {
  it('omits reads segment and synthesis sentence', () => {
    const result = composeBrief({ ...baseInputs, picks: [] });
    expect(result).not.toContain('The future of distributed systems');
    expect(result).not.toContain('dig into');
    expect(result).not.toContain('Also surfaced');
    expect(result.trim().endsWith(REFLECTION)).toBe(true);
  });
});

// ── Guest mode ────────────────────────────────────────────────────────────

describe('composeBrief – guest mode', () => {
  it('renders using insight fields when provided (guest insight has morning_note)', () => {
    const guestInsight: InsightResponse = {
      ...baseInsight,
      greeting: 'Good morning. Your baseline looks stable - keep the day simple and consistent.',
      morning_note: 'Fuel early, hydrate, and choose low-friction wins.',
    };
    const result = composeBrief({
      insight: guestInsight,
      events: [],
      overdueTasks: [],
      picks: [],
      annotations: {},
    });
    expect(result).toContain('Fuel early');
    expect(result.trim().endsWith(REFLECTION)).toBe(true);
  });
});
