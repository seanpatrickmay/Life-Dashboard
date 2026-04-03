// @vitest-environment jsdom
import { describe, expect, it, beforeEach } from 'vitest';
import {
  loadProfile,
  recordRead,
  getAffinityScore,
  recordDismiss,
  getDismissPenalty,
  getTopCategories,
  getCategoryDistribution,
  saveArticle,
  unsaveArticle,
  isArticleSaved,
  dismissArticle,
  isDismissed,
} from './interestProfile';

const PROFILE_KEY = 'ld_interest_profile';

beforeEach(() => { localStorage.clear(); });

describe('three-tier profile structure', () => {
  it('creates empty profile with three layers and correct half-lives', () => {
    const profile = loadProfile();
    expect(profile.version).toBe(2);
    expect(profile.ephemeral.halfLifeDays).toBe(3);
    expect(profile.contextual.halfLifeDays).toBe(21);
    expect(profile.stable.halfLifeDays).toBe(120);
    expect(profile.ephemeral.categoryAffinity).toEqual({});
    expect(profile.contextual.categoryAffinity).toEqual({});
    expect(profile.stable.categoryAffinity).toEqual({});
    expect(profile.dismissHistory).toEqual([]);
    expect(profile.totalReadsAllTime).toBe(0);
  });

  it('recordRead updates all three layers', () => {
    recordRead('tech', 'Hacker News');
    const profile = loadProfile();
    expect(profile.ephemeral.categoryAffinity['tech']?.reads).toBe(1);
    expect(profile.contextual.categoryAffinity['tech']?.reads).toBe(1);
    expect(profile.stable.categoryAffinity['tech']?.reads).toBe(1);
    expect(profile.ephemeral.sourceAffinity['Hacker News']?.reads).toBe(1);
    expect(profile.totalReadsAllTime).toBe(1);
  });

  it('getAffinityScore returns neutral 0.5 with no history', () => {
    expect(getAffinityScore('tech', 'HN')).toBe(0.5);
  });

  it('getAffinityScore returns > 0 after reading', () => {
    recordRead('tech', 'HN');
    const score = getAffinityScore('tech', 'HN');
    expect(score).toBeGreaterThan(0);
    expect(score).toBeLessThanOrEqual(1);
  });
});

describe('v1 profile migration', () => {
  it('migrates legacy flat profile into contextual layer', () => {
    const now = new Date().toISOString();
    localStorage.setItem(PROFILE_KEY, JSON.stringify({
      categoryAffinity: { tech: { reads: 5, lastReadAt: now }, science: { reads: 3, lastReadAt: now } },
      sourceAffinity: { 'HN': { reads: 4, lastReadAt: now } },
      savedArticleIds: ['a1', 'a2'],
      dismissedArticleIds: ['d1'],
      totalReadsAllTime: 8,
      updatedAt: now,
    }));

    const profile = loadProfile();
    expect(profile.version).toBe(2);
    expect(profile.contextual.categoryAffinity['tech']?.reads).toBe(5);
    expect(profile.contextual.categoryAffinity['science']?.reads).toBe(3);
    expect(profile.contextual.sourceAffinity['HN']?.reads).toBe(4);
    expect(profile.savedArticleIds).toEqual(['a1', 'a2']);
    expect(profile.dismissedArticleIds).toEqual(['d1']);
    expect(profile.totalReadsAllTime).toBe(8);
    // Ephemeral and stable should be empty after migration
    expect(profile.ephemeral.categoryAffinity).toEqual({});
    expect(profile.stable.categoryAffinity).toEqual({});
    expect(profile.dismissHistory).toEqual([]);
  });

  it('persists migrated profile so migration only runs once', () => {
    localStorage.setItem(PROFILE_KEY, JSON.stringify({
      categoryAffinity: { tech: { reads: 1, lastReadAt: new Date().toISOString() } },
      sourceAffinity: {},
      savedArticleIds: [],
      dismissedArticleIds: [],
      totalReadsAllTime: 1,
      updatedAt: new Date().toISOString(),
    }));

    loadProfile(); // triggers migration
    const raw = JSON.parse(localStorage.getItem(PROFILE_KEY)!);
    expect(raw.version).toBe(2);
  });
});

describe('dismiss penalties', () => {
  it('recordDismiss stores dismiss history entry', () => {
    recordDismiss('tech', 'HN', 'article-1');
    const profile = loadProfile();
    expect(profile.dismissHistory).toHaveLength(1);
    expect(profile.dismissHistory[0].category).toBe('tech');
    expect(profile.dismissHistory[0].sourceName).toBe('HN');
    expect(profile.dismissedArticleIds).toContain('article-1');
  });

  it('getDismissPenalty returns negative value for dismissed category', () => {
    recordDismiss('tech', 'HN', 'article-1');
    const penalty = getDismissPenalty('tech', 'HN');
    expect(penalty).toBeLessThan(0);
  });

  it('getDismissPenalty returns 0 for unrelated category', () => {
    recordDismiss('tech', 'HN', 'article-1');
    const penalty = getDismissPenalty('science', 'Nature');
    expect(penalty).toBe(0);
  });

  it('does not penalize across categories from same source', () => {
    recordDismiss('tech', 'HN', 'article-1');
    const penalty = getDismissPenalty('science', 'HN');
    expect(penalty).toBe(0);
  });

  it('dismiss penalty decays over 30 days', () => {
    const profile = loadProfile();
    const oldDate = new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString();
    profile.dismissHistory = [{
      category: 'tech',
      sourceName: 'HN',
      articleId: 'old',
      dismissedAt: oldDate,
    }];
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    const penalty = getDismissPenalty('tech', 'HN');
    expect(Math.abs(penalty)).toBeLessThan(0.6);
  });

  it('clamps penalty at -1.0', () => {
    for (let i = 0; i < 10; i++) {
      recordDismiss('tech', 'HN', `article-${i}`);
    }
    const penalty = getDismissPenalty('tech', 'HN');
    expect(penalty).toBeGreaterThanOrEqual(-1.0);
  });
});

describe('getTopCategories', () => {
  it('returns top N categories by reads in stable layer', () => {
    recordRead('tech', 'HN');
    recordRead('tech', 'HN');
    recordRead('tech', 'HN');
    recordRead('science', 'Nature');
    recordRead('science', 'Nature');
    recordRead('world', 'BBC');
    const top = getTopCategories(2);
    expect(top).toEqual(['tech', 'science']);
  });

  it('returns empty array with no history', () => {
    expect(getTopCategories(3)).toEqual([]);
  });
});

describe('getCategoryDistribution', () => {
  it('returns proportions normalized by totalReadsAllTime', () => {
    recordRead('tech', 'HN');
    recordRead('tech', 'HN');
    recordRead('science', 'Nature');
    const dist = getCategoryDistribution();
    expect(dist['tech']).toBeCloseTo(2 / 3, 1);
    expect(dist['science']).toBeCloseTo(1 / 3, 1);
  });
});

describe('save/unsave/dismiss (legacy API)', () => {
  it('saves and unsaves articles', () => {
    saveArticle('a1');
    expect(isArticleSaved('a1')).toBe(true);
    unsaveArticle('a1');
    expect(isArticleSaved('a1')).toBe(false);
  });

  it('dismisses articles via legacy function', () => {
    dismissArticle('a1');
    expect(isDismissed('a1')).toBe(true);
  });
});
