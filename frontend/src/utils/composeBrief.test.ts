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

// ── Synthesis sentence: good readiness + top read ─────────────────────────

describe('composeBrief – synthesis sentence (good readiness)', () => {
  it('connects good readiness to top read with annotation', () => {
    const result = composeBrief(baseInputs);
    // Should have a sentence bridging readiness and the article, not just list them
    expect(result).toContain('The future of distributed systems');
    // The annotation text should appear, not just the title alone
    expect(result).toContain('relevant to your current projects');
  });

  it('does NOT produce a bare value list (readiness score + article title without bridge)', () => {
    const result = composeBrief(baseInputs);
    // Fails if text is merely "Readiness 78/100. The future of distributed systems."
    const scoreIdx = result.indexOf('78');
    const titleIdx = result.indexOf('The future of distributed systems');
    // They should either not be adjacent bare values OR the synthesis sentence
    // wraps them — we verify by checking a connecting phrase exists
    expect(
      result.includes('dig into') ||
      result.includes('worth a look') ||
      result.includes('stands out') ||
      result.includes('standout read') ||
      result.includes('fits a') ||
      result.includes('relevant to')
    ).toBe(true);
    // The title must not appear as first word right after a period following the score
    const barePattern = /\d+\/100\.\s+"The future/;
    expect(barePattern.test(result)).toBe(false);
  });
});

// ── Synthesis sentence: low readiness + relevant read ─────────────────────

describe('composeBrief – synthesis sentence (low readiness)', () => {
  it('connects low readiness to top read when readiness_label is low', () => {
    const lowInsight: InsightResponse = {
      ...baseInsight,
      readiness_score: 42,
      readiness_label: 'Strained',
      morning_note: 'Take it easy today.',
    };
    const result = composeBrief({ ...baseInputs, insight: lowInsight });
    expect(result).toContain('The future of distributed systems');
    // Should suggest gentle/recovery framing, not just state two values
    expect(
      result.includes('recovery') ||
      result.includes('lighter') ||
      result.includes('slower') ||
      result.includes('priority')
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
      isGuest: true,
    });
    expect(result).toContain('Fuel early');
    expect(result.trim().endsWith(REFLECTION)).toBe(true);
  });
});
