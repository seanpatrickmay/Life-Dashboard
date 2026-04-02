// @vitest-environment jsdom
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';

import {
  extractKeywordsFromContext,
  keywordRelevance,
  getSources,
  saveSources,
  getUnsurfacedArticles,
  getTopPerCategory,
  getAllByCategory,
  markArticleRead,
  hasArticles,
  getLastRefresh,
  refreshFeed,
  type NewsArticle,
  type FeedSource,
  type Category,
} from './newsFeedService';

// ── Helpers ──────────────────────────────────────────────────────────────

const STORAGE_KEY = 'ld_news_feed';
const SOURCES_KEY = 'ld_news_sources';

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

function seedStorage(articles: NewsArticle[], lastRefresh: string | null = null) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ articles, lastRefresh }));
}

function readStorage(): { articles: NewsArticle[]; lastRefresh: string | null } {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : { articles: [], lastRefresh: null };
}

// ── Setup ────────────────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

// ── keywordRelevance ─────────────────────────────────────────────────────

describe('keywordRelevance', () => {
  it('returns 0 when no keywords provided', () => {
    const score = keywordRelevance({ title: 'Anything', summary: 'whatever' }, []);
    expect(score).toBe(0);
  });

  it('returns 0 when no keywords match', () => {
    const score = keywordRelevance(
      { title: 'Quantum physics breakthrough', summary: 'Scientists discover new particle' },
      ['cooking', 'recipes', 'baking']
    );
    expect(score).toBe(0);
  });

  it('returns 1.0 when all keywords match', () => {
    const score = keywordRelevance(
      { title: 'New machine learning framework released', summary: null },
      ['machine', 'learning', 'framework']
    );
    expect(score).toBe(1.0);
  });

  it('scores proportionally to fraction of keywords matched', () => {
    const score = keywordRelevance(
      { title: 'Python tutorial', summary: 'Learn python basics' },
      ['python', 'javascript', 'rust', 'golang']
    );
    expect(score).toBeCloseTo(0.25, 2);
  });

  it('matches multi-word keywords as substring', () => {
    const score = keywordRelevance(
      { title: 'The rise of machine learning in healthcare', summary: null },
      ['machine learning']
    );
    expect(score).toBe(1.0);
  });

  it('is case-insensitive', () => {
    const score = keywordRelevance(
      { title: 'PYTHON Release Notes', summary: null },
      ['python']
    );
    expect(score).toBeGreaterThan(0);
  });

  it('uses both title and summary for matching', () => {
    const score = keywordRelevance(
      { title: 'Breaking news', summary: 'A big python update was released today' },
      ['python']
    );
    expect(score).toBeGreaterThan(0);
  });

  it('handles null summary', () => {
    const score = keywordRelevance({ title: 'Test', summary: null }, ['test']);
    expect(score).toBeGreaterThan(0);
  });

  it('caps score at 1.0 even with many matches', () => {
    const score = keywordRelevance(
      { title: 'python rust', summary: 'python and rust are great' },
      ['python', 'rust']
    );
    expect(score).toBeLessThanOrEqual(1.0);
  });
});

// ── extractKeywordsFromContext ────────────────────────────────────────────

describe('extractKeywordsFromContext', () => {
  it('returns empty array for empty input', () => {
    expect(extractKeywordsFromContext([], [])).toEqual([]);
  });

  it('filters out stop words', () => {
    const keywords = extractKeywordsFromContext(
      ['the quick brown fox and the lazy dog'],
      []
    );
    expect(keywords).not.toContain('the');
    expect(keywords).not.toContain('and');
  });

  it('filters out short words (< 3 chars)', () => {
    const keywords = extractKeywordsFromContext(['I am a go to AI ML person'], []);
    expect(keywords).not.toContain('am');
    expect(keywords).not.toContain('go');
    expect(keywords).not.toContain('to');
  });

  it('extracts meaningful words from todos', () => {
    const keywords = extractKeywordsFromContext(
      ['Build React dashboard', 'Deploy kubernetes cluster', 'Study machine learning'],
      []
    );
    expect(keywords).toContain('react');
    expect(keywords).toContain('dashboard');
    expect(keywords).toContain('kubernetes');
    expect(keywords).toContain('machine');
    expect(keywords).toContain('learning');
  });

  it('combines todos and projects', () => {
    const keywords = extractKeywordsFromContext(
      ['Write python script'],
      ['Life Dashboard project']
    );
    expect(keywords).toContain('python');
    expect(keywords).toContain('script');
    expect(keywords).toContain('life');
    expect(keywords).toContain('dashboard');
    expect(keywords).toContain('project');
  });

  it('returns keywords sorted by frequency', () => {
    const keywords = extractKeywordsFromContext(
      ['python python python', 'rust rust', 'golang'],
      []
    );
    expect(keywords[0]).toBe('python');
    expect(keywords[1]).toBe('rust');
    expect(keywords[2]).toBe('golang');
  });

  it('returns at most 40 keywords', () => {
    const manyWords = Array.from({ length: 100 }, (_, i) => `uniqueword${i}`);
    const keywords = extractKeywordsFromContext(manyWords, []);
    expect(keywords.length).toBeLessThanOrEqual(40);
  });

  it('lowercases all keywords', () => {
    const keywords = extractKeywordsFromContext(['Build React Dashboard'], []);
    keywords.forEach(k => expect(k).toBe(k.toLowerCase()));
  });
});

// ── getSources / saveSources ─────────────────────────────────────────────

describe('getSources / saveSources', () => {
  it('returns default sources when nothing stored', () => {
    const sources = getSources();
    expect(sources.length).toBeGreaterThanOrEqual(9);
    expect(sources[0].name).toBe('Hacker News');
    expect(sources.every(s => s.enabled)).toBe(true);
    expect(sources.every(s => 'category' in s)).toBe(true);
  });

  it('default sources span multiple categories', () => {
    const sources = getSources();
    const categories = new Set(sources.map(s => s.category));
    expect(categories.size).toBeGreaterThanOrEqual(5);
    expect(categories.has('tech')).toBe(true);
    expect(categories.has('science')).toBe(true);
    expect(categories.has('world')).toBe(true);
    expect(categories.has('culture')).toBe(true);
    expect(categories.has('business')).toBe(true);
  });

  it('returns stored sources after saving', () => {
    const custom: FeedSource[] = [
      { url: 'https://example.com/feed', name: 'My Feed', category: 'tech', enabled: true },
    ];
    saveSources(custom);
    const loaded = getSources();
    expect(loaded).toEqual(custom);
  });

  it('returns defaults if localStorage is corrupted', () => {
    localStorage.setItem(SOURCES_KEY, 'not valid json!!!');
    const sources = getSources();
    expect(sources.length).toBeGreaterThanOrEqual(9);
  });

  it('returns defaults if stored sources lack category field', () => {
    // Old-format sources without category
    localStorage.setItem(SOURCES_KEY, JSON.stringify([
      { url: 'https://old.com/feed', name: 'Old Feed', enabled: true },
    ]));
    const sources = getSources();
    // Should return defaults since stored sources don't have category
    expect(sources.length).toBeGreaterThanOrEqual(9);
    expect(sources.every(s => 'category' in s)).toBe(true);
  });
});

// ── getTopPerCategory ────────────────────────────────────────────────────

describe('getTopPerCategory', () => {
  it('returns empty array when no articles exist', () => {
    expect(getTopPerCategory()).toEqual([]);
  });

  it('returns one article per category', () => {
    seedStorage([
      makeArticle({ id: 'tech1', category: 'tech', relevanceScore: 0.8 }),
      makeArticle({ id: 'tech2', category: 'tech', relevanceScore: 0.5 }),
      makeArticle({ id: 'sci1', category: 'science', relevanceScore: 0.7 }),
      makeArticle({ id: 'world1', category: 'world', relevanceScore: 0.6 }),
    ]);

    const picks = getTopPerCategory();
    expect(picks.length).toBe(3);
    const categories = picks.map(a => a.category);
    expect(new Set(categories).size).toBe(3);
  });

  it('picks the highest-scored article per category', () => {
    seedStorage([
      makeArticle({ id: 'tech-high', category: 'tech', relevanceScore: 0.9 }),
      makeArticle({ id: 'tech-low', category: 'tech', relevanceScore: 0.2 }),
    ]);

    const picks = getTopPerCategory();
    expect(picks.length).toBe(1);
    expect(picks[0].id).toBe('tech-high');
  });

  it('skips read articles', () => {
    seedStorage([
      makeArticle({ id: 'read', category: 'tech', readAt: '2026-03-18T00:00:00Z' }),
      makeArticle({ id: 'unread', category: 'tech' }),
    ]);

    const picks = getTopPerCategory();
    expect(picks.length).toBe(1);
    expect(picks[0].id).toBe('unread');
  });
});

// ── getAllByCategory ─────────────────────────────────────────────────────

describe('getAllByCategory', () => {
  it('returns empty categories when no articles', () => {
    const result = getAllByCategory();
    expect(result.tech).toEqual([]);
    expect(result.science).toEqual([]);
    expect(result.world).toEqual([]);
  });

  it('groups articles by category', () => {
    seedStorage([
      makeArticle({ id: 'tech1', category: 'tech' }),
      makeArticle({ id: 'tech2', category: 'tech' }),
      makeArticle({ id: 'sci1', category: 'science' }),
    ]);

    const result = getAllByCategory();
    expect(result.tech.length).toBe(2);
    expect(result.science.length).toBe(1);
    expect(result.world.length).toBe(0);
  });

  it('skips read articles', () => {
    seedStorage([
      makeArticle({ id: 'read', category: 'tech', readAt: '2026-03-18T00:00:00Z' }),
      makeArticle({ id: 'unread', category: 'tech' }),
    ]);

    const result = getAllByCategory();
    expect(result.tech.length).toBe(1);
    expect(result.tech[0].id).toBe('unread');
  });

  it('sorts by relevance within category', () => {
    seedStorage([
      makeArticle({ id: 'low', category: 'tech', relevanceScore: 0.2 }),
      makeArticle({ id: 'high', category: 'tech', relevanceScore: 0.9 }),
    ]);

    const result = getAllByCategory();
    expect(result.tech[0].id).toBe('high');
    expect(result.tech[1].id).toBe('low');
  });
});

// ── getUnsurfacedArticles ────────────────────────────────────────────────

describe('getUnsurfacedArticles', () => {
  it('returns empty array when no articles exist', () => {
    expect(getUnsurfacedArticles()).toEqual([]);
  });

  it('returns unsurfaced, unread articles sorted by relevance', () => {
    seedStorage([
      makeArticle({ id: 'low', relevanceScore: 0.2, title: 'Low' }),
      makeArticle({ id: 'high', relevanceScore: 0.9, title: 'High' }),
      makeArticle({ id: 'mid', relevanceScore: 0.5, title: 'Mid' }),
    ]);

    const articles = getUnsurfacedArticles();
    expect(articles.map(a => a.id)).toEqual(['high', 'mid', 'low']);
  });

  it('skips already-surfaced articles', () => {
    seedStorage([
      makeArticle({ id: 'surfaced', surfacedAt: '2026-03-18T00:00:00Z' }),
      makeArticle({ id: 'fresh' }),
    ]);

    const articles = getUnsurfacedArticles();
    expect(articles.length).toBe(1);
    expect(articles[0].id).toBe('fresh');
  });

  it('skips already-read articles', () => {
    seedStorage([
      makeArticle({ id: 'read', readAt: '2026-03-18T00:00:00Z' }),
      makeArticle({ id: 'unread' }),
    ]);

    const articles = getUnsurfacedArticles();
    expect(articles.length).toBe(1);
    expect(articles[0].id).toBe('unread');
  });

  it('respects the limit parameter', () => {
    seedStorage(
      Array.from({ length: 20 }, (_, i) => makeArticle({ id: `art-${i}` }))
    );

    expect(getUnsurfacedArticles(3).length).toBe(3);
    expect(getUnsurfacedArticles(10).length).toBe(10);
  });

  it('marks returned articles as surfaced in storage', () => {
    seedStorage([
      makeArticle({ id: 'a1' }),
      makeArticle({ id: 'a2' }),
    ]);

    getUnsurfacedArticles();

    const state = readStorage();
    expect(state.articles.find(a => a.id === 'a1')?.surfacedAt).toBeTruthy();
    expect(state.articles.find(a => a.id === 'a2')?.surfacedAt).toBeTruthy();
  });

  it('does not re-surface articles on second call', () => {
    seedStorage([
      makeArticle({ id: 'a1' }),
      makeArticle({ id: 'a2' }),
    ]);

    getUnsurfacedArticles();
    const second = getUnsurfacedArticles();
    expect(second.length).toBe(0);
  });

  it('breaks ties by fetchedAt (most recent first)', () => {
    seedStorage([
      makeArticle({ id: 'old', relevanceScore: 0.5, fetchedAt: '2026-03-01T00:00:00Z' }),
      makeArticle({ id: 'new', relevanceScore: 0.5, fetchedAt: '2026-03-18T00:00:00Z' }),
    ]);

    const articles = getUnsurfacedArticles();
    expect(articles[0].id).toBe('new');
    expect(articles[1].id).toBe('old');
  });
});

// ── markArticleRead ──────────────────────────────────────────────────────

describe('markArticleRead', () => {
  it('sets readAt timestamp on the article', () => {
    seedStorage([makeArticle({ id: 'target' })]);

    markArticleRead('target');

    const state = readStorage();
    const article = state.articles.find(a => a.id === 'target');
    expect(article?.readAt).toBeTruthy();
    expect(new Date(article!.readAt!).getTime()).toBeGreaterThan(0);
  });

  it('does not affect other articles', () => {
    seedStorage([
      makeArticle({ id: 'target' }),
      makeArticle({ id: 'other' }),
    ]);

    markArticleRead('target');

    const state = readStorage();
    expect(state.articles.find(a => a.id === 'other')?.readAt).toBeNull();
  });

  it('is idempotent (calling twice does not error)', () => {
    seedStorage([makeArticle({ id: 'target' })]);

    markArticleRead('target');
    markArticleRead('target');

    const state = readStorage();
    expect(state.articles.find(a => a.id === 'target')?.readAt).toBeTruthy();
  });

  it('does nothing if article ID does not exist', () => {
    seedStorage([makeArticle({ id: 'existing' })]);

    markArticleRead('nonexistent');

    const state = readStorage();
    expect(state.articles.length).toBe(1);
    expect(state.articles[0].readAt).toBeNull();
  });
});

// ── hasArticles ──────────────────────────────────────────────────────────

describe('hasArticles', () => {
  it('returns false when storage is empty', () => {
    expect(hasArticles()).toBe(false);
  });

  it('returns true when unread articles exist', () => {
    seedStorage([makeArticle()]);
    expect(hasArticles()).toBe(true);
  });

  it('returns true when surfaced but unread articles exist', () => {
    seedStorage([makeArticle({ surfacedAt: '2026-03-18T00:00:00Z' })]);
    expect(hasArticles()).toBe(true);
  });

  it('returns false when all articles are read', () => {
    seedStorage([makeArticle({ readAt: '2026-03-18T00:00:00Z' })]);
    expect(hasArticles()).toBe(false);
  });

  it('returns true if at least one article is unread', () => {
    seedStorage([
      makeArticle({ id: 'read', readAt: '2026-03-18T00:00:00Z' }),
      makeArticle({ id: 'unread' }),
    ]);
    expect(hasArticles()).toBe(true);
  });
});

// ── getLastRefresh ───────────────────────────────────────────────────────

describe('getLastRefresh', () => {
  it('returns null when never refreshed', () => {
    expect(getLastRefresh()).toBeNull();
  });

  it('returns the stored lastRefresh timestamp', () => {
    const ts = '2026-03-18T12:00:00.000Z';
    seedStorage([], ts);
    expect(getLastRefresh()).toBe(ts);
  });
});

// ── localStorage resilience ──────────────────────────────────────────────

describe('localStorage resilience', () => {
  it('getUnsurfacedArticles handles corrupted storage gracefully', () => {
    localStorage.setItem(STORAGE_KEY, 'not json');
    expect(getUnsurfacedArticles()).toEqual([]);
  });

  it('hasArticles handles corrupted storage gracefully', () => {
    localStorage.setItem(STORAGE_KEY, '{bad');
    expect(hasArticles()).toBe(false);
  });

  it('markArticleRead handles empty storage', () => {
    markArticleRead('nonexistent');
    const state = readStorage();
    expect(state.articles).toEqual([]);
  });

  it('getTopPerCategory handles corrupted storage', () => {
    localStorage.setItem(STORAGE_KEY, 'not json');
    expect(getTopPerCategory()).toEqual([]);
  });

  it('getAllByCategory handles corrupted storage', () => {
    localStorage.setItem(STORAGE_KEY, '{bad');
    const result = getAllByCategory();
    expect(result.tech).toEqual([]);
    expect(result.science).toEqual([]);
  });
});

// ── saveState truncation ─────────────────────────────────────────────────

describe('storage size limit', () => {
  it('truncates to 500 articles when exceeding limit', () => {
    const articles = Array.from({ length: 550 }, (_, i) =>
      makeArticle({
        id: `art-${i}`,
        fetchedAt: new Date(2026, 2, 18, 0, 0, i).toISOString(),
      })
    );
    seedStorage(articles);

    // Trigger a save by surfacing articles (which calls saveState internally)
    getUnsurfacedArticles(1);

    const state = readStorage();
    expect(state.articles.length).toBeLessThanOrEqual(500);
  });

  it('preserves read articles during truncation', () => {
    const readArticles = Array.from({ length: 10 }, (_, i) =>
      makeArticle({
        id: `read-${i}`,
        readAt: '2026-03-18T00:00:00Z',
        fetchedAt: new Date(2026, 0, 1).toISOString(),
      })
    );
    const unreadArticles = Array.from({ length: 500 }, (_, i) =>
      makeArticle({
        id: `unread-${i}`,
        fetchedAt: new Date(2026, 2, 18, 0, 0, i).toISOString(),
      })
    );
    seedStorage([...readArticles, ...unreadArticles]);

    getUnsurfacedArticles(1); // triggers saveState

    const state = readStorage();
    const readCount = state.articles.filter(a => a.readAt).length;
    expect(readCount).toBe(10);
    expect(state.articles.length).toBeLessThanOrEqual(500);
  });
});

// ── refreshFeed ──────────────────────────────────────────────────────────

describe('refreshFeed', () => {
  const SAMPLE_RSS_JSON = {
    status: 'ok',
    items: [
      {
        title: 'RSS Article One',
        link: 'https://example.com/rss-1',
        description: 'First RSS article about python programming',
        pubDate: 'Mon, 18 Mar 2026 12:00:00 GMT',
      },
      {
        title: 'RSS Article Two',
        link: 'https://example.com/rss-2',
        description: 'Second article about rust language',
      },
    ],
  };

  const SAMPLE_WIKIPEDIA = {
    tfa: {
      titles: { normalized: 'Featured Page' },
      extract: 'This is the featured article about quantum computing',
      content_urls: { desktop: { page: 'https://en.wikipedia.org/wiki/Featured' } },
    },
    onthisday: [
      {
        year: 1969,
        text: 'Apollo 11 lands on the moon',
        pages: [{
          titles: { normalized: 'Apollo 11' },
          content_urls: { desktop: { page: 'https://en.wikipedia.org/wiki/Apollo_11' } },
          extract: 'Apollo 11 was the spaceflight...',
        }],
      },
    ],
    mostread: {
      articles: [
        {
          titles: { normalized: 'Trending One' },
          extract: 'First trending article',
          content_urls: { desktop: { page: 'https://en.wikipedia.org/wiki/Trending1' } },
        },
        {
          titles: { normalized: 'Trending Two' },
          extract: 'Second trending article',
          content_urls: { desktop: { page: 'https://en.wikipedia.org/wiki/Trending2' } },
        },
      ],
    },
  };

  function mockFetch(rssJson: object, wikiJson: object) {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('rss2json.com')) {
        return new Response(JSON.stringify(rssJson), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('wikimedia.org')) {
        return new Response(JSON.stringify(wikiJson), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('', { status: 404 });
    });
  }

  beforeEach(() => {
    saveSources([{ url: 'https://test.com/feed', name: 'Test Feed', category: 'tech', enabled: true }]);
  });

  it('fetches RSS and Wikipedia articles', async () => {
    mockFetch(SAMPLE_RSS_JSON, SAMPLE_WIKIPEDIA);

    const result = await refreshFeed([]);

    // 2 RSS + 1 featured + 1 onthisday + 2 trending = 6
    expect(result.newCount).toBe(6);
    expect(result.articles.length).toBe(6);
  });

  it('stores articles in localStorage after refresh', async () => {
    mockFetch(SAMPLE_RSS_JSON, SAMPLE_WIKIPEDIA);

    await refreshFeed([]);

    const state = readStorage();
    expect(state.articles.length).toBe(6);
    expect(state.lastRefresh).toBeTruthy();
  });

  it('assigns correct categories to articles', async () => {
    mockFetch(SAMPLE_RSS_JSON, SAMPLE_WIKIPEDIA);

    const result = await refreshFeed([]);

    const rssArticles = result.articles.filter(a => a.sourceType === 'rss');
    expect(rssArticles.every(a => a.category === 'tech')).toBe(true);

    const historyArticles = result.articles.filter(a => a.category === 'history');
    expect(historyArticles.length).toBe(1);
    expect(historyArticles[0].sourceName).toBe('On This Day');

    const wikiArticles = result.articles.filter(a => a.category === 'wikipedia');
    expect(wikiArticles.length).toBeGreaterThanOrEqual(2);
  });

  it('deduplicates articles by URL on repeated refresh', async () => {
    mockFetch(SAMPLE_RSS_JSON, SAMPLE_WIKIPEDIA);

    await refreshFeed([]);
    const result2 = await refreshFeed([]);

    expect(result2.newCount).toBe(0);
    expect(result2.articles.length).toBe(6);
  });

  it('assigns relevance scores based on keywords', async () => {
    mockFetch(SAMPLE_RSS_JSON, SAMPLE_WIKIPEDIA);

    const result = await refreshFeed(['python']);

    const pythonArticle = result.articles.find(a => a.title === 'RSS Article One');
    const rustArticle = result.articles.find(a => a.title === 'RSS Article Two');

    expect(pythonArticle).toBeTruthy();
    expect(rustArticle).toBeTruthy();
    expect(pythonArticle!.relevanceScore).toBeGreaterThan(rustArticle!.relevanceScore);
  });

  it('handles RSS fetch failure gracefully (falls back to allorigins)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('rss2json.com')) {
        return new Response('', { status: 500 });
      }
      if (url.includes('allorigins.win')) {
        return new Response('', { status: 500 });
      }
      if (url.includes('wikimedia.org')) {
        return new Response(JSON.stringify(SAMPLE_WIKIPEDIA), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('', { status: 404 });
    });

    const result = await refreshFeed([]);
    // Only Wikipedia articles (1 featured + 1 onthisday + 2 trending = 4)
    expect(result.newCount).toBe(4);
  });

  it('handles Wikipedia fetch failure gracefully', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('rss2json.com')) {
        return new Response(JSON.stringify(SAMPLE_RSS_JSON), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('wikimedia.org')) {
        return new Response('', { status: 500 });
      }
      return new Response('', { status: 404 });
    });

    const result = await refreshFeed([]);
    expect(result.newCount).toBe(2);
  });

  it('handles complete network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'));

    const result = await refreshFeed([]);
    expect(result.newCount).toBe(0);
    expect(result.articles.length).toBe(0);
  });

  it('only processes enabled sources', async () => {
    saveSources([
      { url: 'https://test.com/feed', name: 'Enabled', category: 'tech', enabled: true },
      { url: 'https://disabled.com/feed', name: 'Disabled', category: 'science', enabled: false },
    ]);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('wikimedia.org')) {
        return new Response(JSON.stringify({ mostread: { articles: [] } }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('rss2json.com')) {
        return new Response(JSON.stringify(SAMPLE_RSS_JSON), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('', { status: 404 });
    });

    await refreshFeed([]);

    const rssCalls = fetchSpy.mock.calls.filter(
      ([url]) => typeof url === 'string' && url.includes('rss2json.com')
    );
    expect(rssCalls.length).toBe(1);
    expect(rssCalls[0][0]).toContain(encodeURIComponent('https://test.com/feed'));
  });

  it('cleans up articles older than 30 days', async () => {
    const oldDate = new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString();
    seedStorage([
      makeArticle({ id: 'old-unread', fetchedAt: oldDate }),
      makeArticle({ id: 'old-read', fetchedAt: oldDate, readAt: oldDate }),
      makeArticle({ id: 'recent', fetchedAt: new Date().toISOString() }),
    ]);

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('wikimedia.org')) {
        return new Response(JSON.stringify({ mostread: { articles: [] } }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('rss2json.com')) {
        return new Response(JSON.stringify({ status: 'ok', items: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('', { status: 404 });
    });

    await refreshFeed([]);

    const state = readStorage();
    const ids = state.articles.map(a => a.id);
    expect(ids).not.toContain('old-unread');
    expect(ids).toContain('old-read');
    expect(ids).toContain('recent');
  });

  it('limits RSS items to 8 per feed', async () => {
    const items = Array.from({ length: 20 }, (_, i) => ({
      title: `Item ${i}`,
      link: `https://example.com/item-${i}`,
      description: `Description ${i}`,
    }));
    const bigFeed = { status: 'ok', items };

    mockFetch(bigFeed, { mostread: { articles: [] } });

    const result = await refreshFeed([]);
    const rssArticles = result.articles.filter(a => a.sourceType === 'rss');
    expect(rssArticles.length).toBe(8);
  });
});
