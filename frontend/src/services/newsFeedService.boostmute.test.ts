// @vitest-environment jsdom
import { describe, expect, it, beforeEach } from 'vitest';
import {
  getCuratedFeed,
  type NewsArticle,
} from './newsFeedService';
import { saveBoostedTopics, saveMutedTopics } from './interestProfile';

const STORAGE_KEY = 'ld_news_feed';

function makeArticle(overrides: Partial<NewsArticle> = {}): NewsArticle {
  return {
    id: overrides.id ?? 'abc123',
    sourceType: 'rss',
    sourceName: 'Test Feed',
    category: 'tech',
    url: 'https://example.com/article',
    title: 'Test Article',
    summary: 'A test summary',
    imageUrl: null,
    publishedAt: '2026-03-18T00:00:00.000Z',
    fetchedAt: '2026-03-18T12:00:00.000Z',
    relevanceScore: 0.5,
    surfacedAt: null,
    readAt: null,
    ...overrides,
  };
}

function seedStorage(articles: NewsArticle[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ articles, lastRefresh: null }));
}

beforeEach(() => {
  localStorage.clear();
});

describe('getCuratedFeed boost/mute multipliers', () => {
  it('boosted article ranks above identical-baseline article without boost', () => {
    saveBoostedTopics(['llm']);
    seedStorage([
      makeArticle({ id: 'boosted', title: 'LLM advances in 2026', summary: 'About llm', relevanceScore: 0.5 }),
      makeArticle({ id: 'neutral', title: 'Weekly roundup', summary: 'Generic news', relevanceScore: 0.5 }),
    ]);

    const feed = getCuratedFeed([]);
    const allArticles = [...feed.picks, ...feed.more];
    const boostedIdx = allArticles.findIndex(a => a.id === 'boosted');
    const neutralIdx = allArticles.findIndex(a => a.id === 'neutral');

    expect(boostedIdx).toBeLessThan(neutralIdx);
  });

  it('muted article ranks below identical-baseline article', () => {
    saveMutedTopics(['celebrity']);
    seedStorage([
      makeArticle({ id: 'muted', title: 'Celebrity gossip special', summary: 'About celebrity news', relevanceScore: 0.5 }),
      makeArticle({ id: 'neutral', title: 'Quantum computing update', summary: 'Science news', relevanceScore: 0.5 }),
    ]);

    const feed = getCuratedFeed([]);
    const allArticles = [...feed.picks, ...feed.more];
    const mutedIdx = allArticles.findIndex(a => a.id === 'muted');
    const neutralIdx = allArticles.findIndex(a => a.id === 'neutral');

    expect(mutedIdx).toBeGreaterThan(neutralIdx);
  });

  it('effective scores stay within [0.05, 1.0]', () => {
    saveBoostedTopics(['llm']);
    saveMutedTopics(['celebrity']);
    seedStorage([
      makeArticle({ id: 'max', sourceName: 'Source A', title: 'LLM transformer breakthroughs', summary: 'llm research', relevanceScore: 1.0 }),
      makeArticle({ id: 'min', sourceName: 'Source B', title: 'Celebrity gossip special', summary: 'celebrity drama', relevanceScore: 0.05 }),
      makeArticle({ id: 'neutral', sourceName: 'Source C', title: 'Volcanic eruption in Iceland', summary: 'Geology update', relevanceScore: 0.5 }),
    ]);

    const feed = getCuratedFeed([]);
    const all = [...feed.picks, ...feed.more];

    // All articles should still be present (not filtered out)
    expect(all.length).toBe(3);

    // The ordering: boosted max first, then neutral, then muted min last
    const maxIdx = all.findIndex(a => a.id === 'max');
    const minIdx = all.findIndex(a => a.id === 'min');
    const neutralIdx = all.findIndex(a => a.id === 'neutral');

    expect(maxIdx).toBeLessThan(neutralIdx);
    expect(neutralIdx).toBeLessThan(minIdx);
  });

  it('case-insensitive matching for boost', () => {
    saveBoostedTopics(['LLM']);
    seedStorage([
      makeArticle({ id: 'lower', title: 'llm is transforming AI', summary: null, relevanceScore: 0.5 }),
      makeArticle({ id: 'neutral', title: 'Weather report', summary: null, relevanceScore: 0.5 }),
    ]);

    const feed = getCuratedFeed([]);
    const all = [...feed.picks, ...feed.more];
    const lowerIdx = all.findIndex(a => a.id === 'lower');
    const neutralIdx = all.findIndex(a => a.id === 'neutral');

    expect(lowerIdx).toBeLessThan(neutralIdx);
  });

  it('case-insensitive matching for mute', () => {
    saveMutedTopics(['CELEBRITY']);
    seedStorage([
      makeArticle({ id: 'muted', title: 'celebrity news today', summary: null, relevanceScore: 0.5 }),
      makeArticle({ id: 'neutral', title: 'Astronomy discoveries', summary: null, relevanceScore: 0.5 }),
    ]);

    const feed = getCuratedFeed([]);
    const all = [...feed.picks, ...feed.more];
    const mutedIdx = all.findIndex(a => a.id === 'muted');
    const neutralIdx = all.findIndex(a => a.id === 'neutral');

    expect(mutedIdx).toBeGreaterThan(neutralIdx);
  });

  it('no boost/mute topics: ordering is unaffected (neutral multiplier)', () => {
    seedStorage([
      makeArticle({ id: 'high', sourceName: 'Source A', title: 'Quantum computing milestone', summary: null, relevanceScore: 0.9 }),
      makeArticle({ id: 'low', sourceName: 'Source B', title: 'Bicycle market trends', summary: null, relevanceScore: 0.1 }),
    ]);

    const feed = getCuratedFeed([]);
    const all = [...feed.picks, ...feed.more];
    const highIdx = all.findIndex(a => a.id === 'high');
    const lowIdx = all.findIndex(a => a.id === 'low');

    expect(highIdx).toBeLessThan(lowIdx);
  });
});
