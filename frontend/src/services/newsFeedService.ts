const STORAGE_KEY = 'ld_news_feed';
const SOURCES_KEY = 'ld_news_sources';

export type Category =
  | 'tech'
  | 'science'
  | 'world'
  | 'culture'
  | 'history'
  | 'business'
  | 'wikipedia';

export const CATEGORY_LABELS: Record<Category, string> = {
  tech: 'Tech',
  science: 'Science',
  world: 'World',
  culture: 'Culture & Arts',
  history: 'History',
  business: 'Business',
  wikipedia: 'Wikipedia',
};

export type NewsArticle = {
  id: string;
  sourceType: 'rss' | 'wikipedia';
  sourceName: string;
  category: Category;
  url: string;
  title: string;
  summary: string | null;
  imageUrl: string | null;
  publishedAt: string | null;
  fetchedAt: string;
  relevanceScore: number;
  surfacedAt: string | null;
  readAt: string | null;
};

export type FeedSource = {
  url: string;
  name: string;
  category: Category;
  enabled: boolean;
};

type StoredState = {
  articles: NewsArticle[];
  lastRefresh: string | null;
};

const DEFAULT_SOURCES: FeedSource[] = [
  // Tech
  { url: 'https://hnrss.org/best', name: 'Hacker News', category: 'tech', enabled: true },
  { url: 'https://feeds.arstechnica.com/arstechnica/index', name: 'Ars Technica', category: 'tech', enabled: true },
  // Science
  { url: 'https://www.nature.com/nature.rss', name: 'Nature', category: 'science', enabled: true },
  { url: 'https://rss.nytimes.com/services/xml/rss/nyt/Science.xml', name: 'NYT Science', category: 'science', enabled: true },
  // World
  { url: 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml', name: 'NYT World', category: 'world', enabled: true },
  { url: 'https://feeds.bbci.co.uk/news/world/rss.xml', name: 'BBC World', category: 'world', enabled: true },
  // Culture & Arts
  { url: 'https://rss.nytimes.com/services/xml/rss/nyt/Books.xml', name: 'NYT Books', category: 'culture', enabled: true },
  { url: 'https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml', name: 'NYT Arts', category: 'culture', enabled: true },
  // Business
  { url: 'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml', name: 'NYT Business', category: 'business', enabled: true },
  // History — sourced via Wikipedia below
];

function hashUrl(url: string): string {
  let hash = 0;
  for (let i = 0; i < url.length; i++) {
    const char = url.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return doc.body.textContent?.trim() || '';
}

function truncate(text: string | null, maxLen = 300): string | null {
  if (!text) return null;
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
}

function loadState(): StoredState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { articles: [], lastRefresh: null };
}

function saveState(state: StoredState): void {
  if (state.articles.length > 500) {
    const read = state.articles.filter(a => a.readAt);
    const unread = state.articles
      .filter(a => !a.readAt)
      .sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt))
      .slice(0, 500 - read.length);
    state.articles = [...read, ...unread].slice(0, 500);
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function getSources(): FeedSource[] {
  try {
    const raw = localStorage.getItem(SOURCES_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].category) return parsed;
    }
  } catch { /* ignore */ }
  return DEFAULT_SOURCES;
}

export function saveSources(sources: FeedSource[]): void {
  localStorage.setItem(SOURCES_KEY, JSON.stringify(sources));
}

// Try rss2json first (more reliable CORS), fall back to allorigins
async function fetchRssViaProxy(feedUrl: string): Promise<Array<{ title: string; url: string; summary: string | null; publishedAt: string | null }>> {
  // Strategy 1: rss2json API
  try {
    const r2jUrl = `https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(feedUrl)}`;
    const resp = await fetch(r2jUrl, { signal: AbortSignal.timeout(10000) });
    if (resp.ok) {
      const data = await resp.json();
      if (data.status === 'ok' && data.items?.length) {
        return data.items.slice(0, 12).map((item: any) => ({
          title: stripHtml(item.title || ''),
          url: item.link || item.guid || '',
          summary: truncate(stripHtml(item.description || '')),
          publishedAt: item.pubDate ? new Date(item.pubDate).toISOString() : null,
        })).filter((item: any) => item.title && item.url);
      }
    }
  } catch { /* fall through */ }

  // Strategy 2: allorigins proxy with XML parsing
  try {
    const proxyUrl = `https://api.allorigins.win/raw?url=${encodeURIComponent(feedUrl)}`;
    const resp = await fetch(proxyUrl, { signal: AbortSignal.timeout(12000) });
    if (!resp.ok) return [];
    const xml = await resp.text();
    const doc = new DOMParser().parseFromString(xml, 'text/xml');

    const items: Array<{ title: string; url: string; summary: string | null; publishedAt: string | null }> = [];
    const rssItems = doc.querySelectorAll('item');
    const atomEntries = doc.querySelectorAll('entry');
    const entries = rssItems.length > 0 ? rssItems : atomEntries;

    entries.forEach((item, i) => {
      if (i >= 12) return;
      const title = item.querySelector('title')?.textContent?.trim();
      const link = item.querySelector('link')?.textContent?.trim()
        || item.querySelector('link')?.getAttribute('href')
        || '';
      const desc = item.querySelector('description')?.textContent
        || item.querySelector('summary')?.textContent
        || item.querySelector('content')?.textContent
        || '';
      const pubDate = item.querySelector('pubDate')?.textContent
        || item.querySelector('published')?.textContent
        || item.querySelector('updated')?.textContent
        || null;

      if (title && link) {
        items.push({
          title: stripHtml(title),
          url: link.trim(),
          summary: truncate(stripHtml(desc)),
          publishedAt: pubDate ? new Date(pubDate).toISOString() : null,
        });
      }
    });

    return items;
  } catch {
    return [];
  }
}

async function fetchWikipediaArticles(): Promise<Array<{ title: string; url: string; summary: string | null; sourceName: string; category: Category }>> {
  const now = new Date();
  const url = `https://api.wikimedia.org/feed/v1/wikipedia/en/featured/${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, '0')}/${String(now.getDate()).padStart(2, '0')}`;

  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(10000) });
    if (!resp.ok) return [];
    const data = await resp.json();
    const articles: Array<{ title: string; url: string; summary: string | null; sourceName: string; category: Category }> = [];

    // Featured article
    const tfa = data.tfa;
    if (tfa) {
      const pageUrl = tfa.content_urls?.desktop?.page;
      if (pageUrl) {
        articles.push({
          title: tfa.titles?.normalized || tfa.title || 'Wikipedia Featured',
          url: pageUrl,
          summary: truncate(tfa.extract),
          sourceName: 'Wikipedia Featured',
          category: 'wikipedia',
        });
      }
    }

    // On this day — history!
    const onThisDay = data.onthisday || [];
    for (const event of onThisDay.slice(0, 4)) {
      const page = event.pages?.[0];
      if (!page) continue;
      const pageUrl = page.content_urls?.desktop?.page;
      if (!pageUrl) continue;
      const yearText = event.year ? `(${event.year}) ` : '';
      articles.push({
        title: page.titles?.normalized || page.title || '',
        url: pageUrl,
        summary: truncate(`${yearText}${event.text || page.extract || ''}`),
        sourceName: 'On This Day',
        category: 'history',
      });
    }

    // Most read (top 6)
    const mostread = data.mostread?.articles || [];
    for (const article of mostread.slice(0, 6)) {
      const pageUrl = article.content_urls?.desktop?.page;
      if (!pageUrl) continue;
      articles.push({
        title: article.titles?.normalized || article.title || '',
        url: pageUrl,
        summary: truncate(article.extract),
        sourceName: 'Wikipedia Trending',
        category: 'wikipedia',
      });
    }

    return articles;
  } catch {
    return [];
  }
}

export function scoreArticle(article: { title: string; summary: string | null }, keywords: string[]): number {
  if (!keywords.length) return 0.1;
  const text = `${article.title} ${article.summary || ''}`.toLowerCase();
  const tokens = new Set(text.split(/\W+/).filter(t => t.length > 2));
  let matches = 0;
  for (const kw of keywords) {
    if (kw.includes(' ')) {
      if (text.includes(kw)) matches++;
    } else if (tokens.has(kw)) {
      matches++;
    }
  }
  return 0.1 + 0.9 * Math.min(matches / Math.max(keywords.length, 1), 1.0);
}

export function extractKeywordsFromContext(todos: string[], projects: string[]): string[] {
  const stopWords = new Set([
    'the', 'and', 'for', 'that', 'this', 'with', 'from', 'have', 'has',
    'been', 'will', 'can', 'are', 'was', 'were', 'not', 'but', 'all',
    'they', 'their', 'what', 'when', 'which', 'who', 'how', 'get', 'set',
    'make', 'need', 'want', 'use', 'new', 'one', 'two', 'also', 'just',
    'more', 'about', 'some', 'into', 'than', 'then', 'them', 'each',
    'other', 'very', 'after', 'before', 'between', 'done', 'todo',
    'check', 'look', 'work', 'start', 'finish', 'update', 'add',
  ]);

  const allText = [...todos, ...projects].join(' ').toLowerCase();
  const words = allText.split(/\W+/).filter(w => w.length > 2 && !stopWords.has(w));

  const freq = new Map<string, number>();
  for (const w of words) {
    freq.set(w, (freq.get(w) || 0) + 1);
  }

  return Array.from(freq.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 40)
    .map(([word]) => word);
}

export async function refreshFeed(keywords: string[]): Promise<{ articles: NewsArticle[]; newCount: number }> {
  const state = loadState();
  const existingUrls = new Set(state.articles.map(a => a.id));
  const now = new Date().toISOString();
  let newCount = 0;

  const sources = getSources().filter(s => s.enabled);

  const rssPromises = sources.map(async (source) => {
    const items = await fetchRssViaProxy(source.url);
    return items.map(item => ({ ...item, sourceName: source.name, category: source.category }));
  });

  const [rssResults, wikiResults] = await Promise.all([
    Promise.all(rssPromises),
    fetchWikipediaArticles(),
  ]);

  for (const feedItems of rssResults) {
    for (const item of feedItems) {
      const id = hashUrl(item.url);
      if (existingUrls.has(id)) continue;
      existingUrls.add(id);

      state.articles.push({
        id,
        sourceType: 'rss',
        sourceName: item.sourceName,
        category: item.category,
        url: item.url,
        title: item.title,
        summary: item.summary,
        imageUrl: null,
        publishedAt: item.publishedAt,
        fetchedAt: now,
        relevanceScore: scoreArticle(item, keywords),
        surfacedAt: null,
        readAt: null,
      });
      newCount++;
    }
  }

  for (const item of wikiResults) {
    const id = hashUrl(item.url);
    if (existingUrls.has(id)) continue;
    existingUrls.add(id);

    state.articles.push({
      id,
      sourceType: 'wikipedia',
      sourceName: item.sourceName,
      category: item.category,
      url: item.url,
      title: item.title,
      summary: item.summary,
      imageUrl: null,
      publishedAt: now,
      fetchedAt: now,
      relevanceScore: scoreArticle(item, keywords),
      surfacedAt: null,
      readAt: null,
    });
    newCount++;
  }

  const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  state.articles = state.articles.filter(
    a => a.readAt || a.fetchedAt > cutoff
  );

  state.lastRefresh = now;
  saveState(state);

  return { articles: state.articles, newCount };
}

export function getUnsurfacedArticles(limit = 8): NewsArticle[] {
  const state = loadState();
  const unsurfaced = state.articles
    .filter(a => !a.surfacedAt && !a.readAt)
    .sort((a, b) => b.relevanceScore - a.relevanceScore || b.fetchedAt.localeCompare(a.fetchedAt))
    .slice(0, limit);

  if (unsurfaced.length > 0) {
    const now = new Date().toISOString();
    const surfacedIds = new Set(unsurfaced.map(a => a.id));
    state.articles = state.articles.map(a =>
      surfacedIds.has(a.id) ? { ...a, surfacedAt: now } : a
    );
    saveState(state);
  }

  return unsurfaced;
}

/** Get the top unread article per category for dashboard display. */
export function getTopPerCategory(): NewsArticle[] {
  const state = loadState();
  const unread = state.articles
    .filter(a => !a.readAt)
    .sort((a, b) => b.relevanceScore - a.relevanceScore || b.fetchedAt.localeCompare(a.fetchedAt));

  const seen = new Set<Category>();
  const picks: NewsArticle[] = [];
  for (const a of unread) {
    if (seen.has(a.category)) continue;
    seen.add(a.category);
    picks.push(a);
  }
  return picks;
}

/** Get all unread articles grouped by category for the news page. */
export function getAllByCategory(): Record<Category, NewsArticle[]> {
  const state = loadState();
  const result: Record<Category, NewsArticle[]> = {
    tech: [], science: [], world: [], culture: [], history: [], business: [], wikipedia: [],
  };

  const unread = state.articles
    .filter(a => !a.readAt)
    .sort((a, b) => b.relevanceScore - a.relevanceScore || b.fetchedAt.localeCompare(a.fetchedAt));

  for (const a of unread) {
    result[a.category]?.push(a);
  }
  return result;
}

export function markArticleRead(articleId: string): void {
  const state = loadState();
  const now = new Date().toISOString();
  state.articles = state.articles.map(a =>
    a.id === articleId ? { ...a, readAt: now } : a
  );
  saveState(state);
}

export function hasArticles(): boolean {
  const state = loadState();
  return state.articles.some(a => !a.readAt);
}

export function getLastRefresh(): string | null {
  return loadState().lastRefresh;
}
