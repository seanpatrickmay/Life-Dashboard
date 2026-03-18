// @vitest-environment jsdom
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';

import {
  extractKeywordsFromContext,
  scoreArticle,
  getSources,
  saveSources,
  getUnsurfacedArticles,
  markArticleRead,
  hasArticles,
  getLastRefresh,
  refreshFeed,
  type NewsArticle,
  type FeedSource,
} from './newsFeedService';

// ── Helpers ──────────────────────────────────────────────────────────────

const STORAGE_KEY = 'ld_news_feed';
const SOURCES_KEY = 'ld_news_sources';

function makeArticle(overrides: Partial<NewsArticle> = {}): NewsArticle {
  return {
    id: overrides.id ?? 'abc123',
    sourceType: 'rss',
    sourceName: 'Test Feed',
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

// ── scoreArticle ─────────────────────────────────────────────────────────

describe('scoreArticle', () => {
  it('returns 0.1 base score when no keywords', () => {
    const score = scoreArticle({ title: 'Anything', summary: 'whatever' }, []);
    expect(score).toBe(0.1);
  });

  it('returns 0.1 when no keywords match', () => {
    const score = scoreArticle(
      { title: 'Quantum physics breakthrough', summary: 'Scientists discover new particle' },
      ['cooking', 'recipes', 'baking']
    );
    expect(score).toBe(0.1);
  });

  it('scores higher when keywords match the title', () => {
    const score = scoreArticle(
      { title: 'New machine learning framework released', summary: null },
      ['machine', 'learning', 'framework']
    );
    expect(score).toBeGreaterThan(0.1);
    // 3 out of 3 keywords match → 0.1 + 0.9 * 1.0 = 1.0
    expect(score).toBe(1.0);
  });

  it('scores proportionally to fraction of keywords matched', () => {
    const score = scoreArticle(
      { title: 'Python tutorial', summary: 'Learn python basics' },
      ['python', 'javascript', 'rust', 'golang']
    );
    // 1 out of 4 keywords match → 0.1 + 0.9 * 0.25 = 0.325
    expect(score).toBeCloseTo(0.325, 2);
  });

  it('matches multi-word keywords as substring', () => {
    const score = scoreArticle(
      { title: 'The rise of machine learning in healthcare', summary: null },
      ['machine learning']
    );
    // multi-word keyword found → 1/1 = 1.0 → 0.1 + 0.9 = 1.0
    expect(score).toBe(1.0);
  });

  it('is case-insensitive', () => {
    const score = scoreArticle(
      { title: 'PYTHON Release Notes', summary: null },
      ['python']
    );
    expect(score).toBeGreaterThan(0.1);
  });

  it('uses both title and summary for matching', () => {
    const scoreTitle = scoreArticle(
      { title: 'Breaking news', summary: 'A big python update was released today' },
      ['python']
    );
    expect(scoreTitle).toBeGreaterThan(0.1);
  });

  it('handles null summary', () => {
    const score = scoreArticle({ title: 'Test', summary: null }, ['test']);
    expect(score).toBeGreaterThan(0.1);
  });

  it('caps score at 1.0 even with many matches', () => {
    // All 2 keywords match → should cap at 1.0
    const score = scoreArticle(
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
    expect(sources.length).toBe(5);
    expect(sources[0].name).toBe('Hacker News Best');
    expect(sources.every(s => s.enabled)).toBe(true);
  });

  it('returns stored sources after saving', () => {
    const custom: FeedSource[] = [
      { url: 'https://example.com/feed', name: 'My Feed', enabled: true },
    ];
    saveSources(custom);
    const loaded = getSources();
    expect(loaded).toEqual(custom);
  });

  it('returns defaults if localStorage is corrupted', () => {
    localStorage.setItem(SOURCES_KEY, 'not valid json!!!');
    const sources = getSources();
    expect(sources.length).toBe(5);
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

    getUnsurfacedArticles(); // surfaces a1, a2
    const second = getUnsurfacedArticles(); // nothing left
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
    // readAt should be a valid ISO date
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

  it('returns true when unsurfaced, unread articles exist', () => {
    seedStorage([makeArticle()]);
    expect(hasArticles()).toBe(true);
  });

  it('returns false when all articles are surfaced', () => {
    seedStorage([makeArticle({ surfacedAt: '2026-03-18T00:00:00Z' })]);
    expect(hasArticles()).toBe(false);
  });

  it('returns false when all articles are read', () => {
    seedStorage([makeArticle({ readAt: '2026-03-18T00:00:00Z' })]);
    expect(hasArticles()).toBe(false);
  });

  it('returns true if at least one article is unsurfaced and unread', () => {
    seedStorage([
      makeArticle({ id: 'surfaced', surfacedAt: '2026-03-18T00:00:00Z' }),
      makeArticle({ id: 'fresh' }),
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
    // Should not throw
    markArticleRead('nonexistent');
    const state = readStorage();
    expect(state.articles).toEqual([]);
  });
});

// ── saveState truncation (via getUnsurfacedArticles roundtrip) ───────────

describe('storage size limit', () => {
  it('truncates to 200 articles when exceeding limit', () => {
    const articles = Array.from({ length: 250 }, (_, i) =>
      makeArticle({
        id: `art-${i}`,
        fetchedAt: new Date(2026, 2, 18, 0, 0, i).toISOString(),
      })
    );
    seedStorage(articles);

    // Trigger a save by surfacing articles (which calls saveState internally)
    getUnsurfacedArticles(1);

    const state = readStorage();
    expect(state.articles.length).toBeLessThanOrEqual(200);
  });

  it('preserves read articles during truncation', () => {
    const readArticles = Array.from({ length: 10 }, (_, i) =>
      makeArticle({
        id: `read-${i}`,
        readAt: '2026-03-18T00:00:00Z',
        fetchedAt: new Date(2026, 0, 1).toISOString(),
      })
    );
    const unreadArticles = Array.from({ length: 200 }, (_, i) =>
      makeArticle({
        id: `unread-${i}`,
        fetchedAt: new Date(2026, 2, 18, 0, 0, i).toISOString(),
      })
    );
    seedStorage([...readArticles, ...unreadArticles]);

    getUnsurfacedArticles(1); // triggers saveState

    const state = readStorage();
    const readCount = state.articles.filter(a => a.readAt).length;
    expect(readCount).toBe(10); // all read articles preserved
    expect(state.articles.length).toBeLessThanOrEqual(200);
  });
});

// ── refreshFeed ──────────────────────────────────────────────────────────

describe('refreshFeed', () => {
  const SAMPLE_RSS = `<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>RSS Article One</title>
      <link>https://example.com/rss-1</link>
      <description>First RSS article about python programming</description>
      <pubDate>Mon, 18 Mar 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>RSS Article Two</title>
      <link>https://example.com/rss-2</link>
      <description>Second article about rust language</description>
    </item>
  </channel>
</rss>`;

  const SAMPLE_ATOM = `<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom Entry</title>
    <link href="https://example.com/atom-1"/>
    <summary>An atom entry about golang</summary>
    <updated>2026-03-18T10:00:00Z</updated>
  </entry>
</feed>`;

  const SAMPLE_WIKIPEDIA = {
    tfa: {
      titles: { normalized: 'Featured Page' },
      extract: 'This is the featured article about quantum computing',
      content_urls: { desktop: { page: 'https://en.wikipedia.org/wiki/Featured' } },
    },
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

  function mockFetch(rssXml: string, wikiJson: object) {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('allorigins.win')) {
        return new Response(rssXml, { status: 200 });
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
    // Use a single source for simpler testing
    saveSources([{ url: 'https://test.com/feed', name: 'Test Feed', enabled: true }]);
  });

  it('fetches RSS and Wikipedia articles', async () => {
    mockFetch(SAMPLE_RSS, SAMPLE_WIKIPEDIA);

    const result = await refreshFeed([]);

    // 2 RSS + 1 featured + 2 trending = 5
    expect(result.newCount).toBe(5);
    expect(result.articles.length).toBe(5);
  });

  it('stores articles in localStorage after refresh', async () => {
    mockFetch(SAMPLE_RSS, SAMPLE_WIKIPEDIA);

    await refreshFeed([]);

    const state = readStorage();
    expect(state.articles.length).toBe(5);
    expect(state.lastRefresh).toBeTruthy();
  });

  it('deduplicates articles by URL on repeated refresh', async () => {
    mockFetch(SAMPLE_RSS, SAMPLE_WIKIPEDIA);

    await refreshFeed([]);
    const result2 = await refreshFeed([]);

    expect(result2.newCount).toBe(0); // all duplicates
    expect(result2.articles.length).toBe(5); // same total
  });

  it('assigns relevance scores based on keywords', async () => {
    mockFetch(SAMPLE_RSS, SAMPLE_WIKIPEDIA);

    const result = await refreshFeed(['python']);

    const pythonArticle = result.articles.find(a => a.title === 'RSS Article One');
    const rustArticle = result.articles.find(a => a.title === 'RSS Article Two');

    expect(pythonArticle).toBeTruthy();
    expect(rustArticle).toBeTruthy();
    // Python article matches keyword, should score higher
    expect(pythonArticle!.relevanceScore).toBeGreaterThan(rustArticle!.relevanceScore);
  });

  it('handles RSS fetch failure gracefully', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
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
    // Only Wikipedia articles (3)
    expect(result.newCount).toBe(3);
  });

  it('handles Wikipedia fetch failure gracefully', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('allorigins.win')) {
        return new Response(SAMPLE_RSS, { status: 200 });
      }
      if (url.includes('wikimedia.org')) {
        return new Response('', { status: 500 });
      }
      return new Response('', { status: 404 });
    });

    const result = await refreshFeed([]);
    // Only RSS articles (2)
    expect(result.newCount).toBe(2);
  });

  it('handles complete network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'));

    const result = await refreshFeed([]);
    expect(result.newCount).toBe(0);
    expect(result.articles.length).toBe(0);
  });

  it('parses Atom feeds correctly', async () => {
    mockFetch(SAMPLE_ATOM, { mostread: { articles: [] } });

    const result = await refreshFeed([]);

    const atomArticle = result.articles.find(a => a.title === 'Atom Entry');
    expect(atomArticle).toBeTruthy();
    expect(atomArticle!.url).toBe('https://example.com/atom-1');
    expect(atomArticle!.summary).toContain('golang');
  });

  it('strips HTML tags from titles and summaries', async () => {
    const rssWithHtml = `<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
  <item>
    <title>&lt;b&gt;Bold Title&lt;/b&gt;</title>
    <link>https://example.com/html</link>
    <description>&lt;p&gt;A &lt;strong&gt;bold&lt;/strong&gt; description&lt;/p&gt;</description>
  </item>
</channel></rss>`;
    mockFetch(rssWithHtml, { mostread: { articles: [] } });

    const result = await refreshFeed([]);
    const article = result.articles.find(a => a.url === 'https://example.com/html');
    expect(article).toBeTruthy();
    expect(article!.title).not.toContain('<');
    expect(article!.summary).not.toContain('<');
  });

  it('only processes enabled sources', async () => {
    saveSources([
      { url: 'https://test.com/feed', name: 'Enabled', enabled: true },
      { url: 'https://disabled.com/feed', name: 'Disabled', enabled: false },
    ]);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('wikimedia.org')) {
        return new Response(JSON.stringify({ mostread: { articles: [] } }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(SAMPLE_RSS, { status: 200 });
    });

    await refreshFeed([]);

    // Should only have fetched for the enabled source (+ wikipedia)
    const rssCalls = fetchSpy.mock.calls.filter(
      ([url]) => typeof url === 'string' && url.includes('allorigins.win')
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
      return new Response('<rss><channel></channel></rss>', { status: 200 });
    });

    await refreshFeed([]);

    const state = readStorage();
    const ids = state.articles.map(a => a.id);
    expect(ids).not.toContain('old-unread'); // old + unread → cleaned
    expect(ids).toContain('old-read');       // old + read → preserved
    expect(ids).toContain('recent');         // recent → preserved
  });

  it('limits RSS items to 15 per feed', async () => {
    const items = Array.from({ length: 20 }, (_, i) => `
      <item>
        <title>Item ${i}</title>
        <link>https://example.com/item-${i}</link>
        <description>Description ${i}</description>
      </item>
    `).join('');
    const bigRss = `<?xml version="1.0"?><rss version="2.0"><channel><title>Big</title>${items}</channel></rss>`;

    mockFetch(bigRss, { mostread: { articles: [] } });

    const result = await refreshFeed([]);
    const rssArticles = result.articles.filter(a => a.sourceType === 'rss');
    expect(rssArticles.length).toBe(15);
  });
});
