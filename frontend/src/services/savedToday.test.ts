// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { recordSavedToday, getSavedTodayCount } from './savedToday';

const STORAGE_KEY = 'news.savedToday';

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  localStorage.clear();
});

describe('recordSavedToday / getSavedTodayCount', () => {
  it('records an article and returns count of 1', () => {
    recordSavedToday('article-1');
    expect(getSavedTodayCount()).toBe(1);
  });

  it('deduplicates: recording the same id twice stays at 1', () => {
    recordSavedToday('article-1');
    recordSavedToday('article-1');
    expect(getSavedTodayCount()).toBe(1);
  });

  it('accumulates multiple distinct ids', () => {
    recordSavedToday('article-1');
    recordSavedToday('article-2');
    recordSavedToday('article-3');
    expect(getSavedTodayCount()).toBe(3);
  });

  it('returns 0 when nothing has been recorded', () => {
    expect(getSavedTodayCount()).toBe(0);
  });

  it('resets to 0 when stored date is a previous day', () => {
    // Pre-seed yesterday's data
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ date: '2020-01-01', ids: ['article-old'] }),
    );
    expect(getSavedTodayCount()).toBe(0);
  });

  it('resets the store and records fresh when stored date is a previous day', () => {
    // Pre-seed yesterday's data
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ date: '2020-01-01', ids: ['article-old'] }),
    );
    recordSavedToday('article-new');
    expect(getSavedTodayCount()).toBe(1);
    // Old article should not be in the new store
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = JSON.parse(raw!);
    expect(parsed.ids).not.toContain('article-old');
    expect(parsed.ids).toContain('article-new');
  });

  it('tolerates a throwing localStorage gracefully (private-mode safety)', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });
    // Should not throw
    expect(() => recordSavedToday('article-1')).not.toThrow();
    expect(getSavedTodayCount()).toBe(0);
  });
});
