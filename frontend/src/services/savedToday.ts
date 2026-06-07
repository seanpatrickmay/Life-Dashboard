/**
 * savedToday — date-keyed localStorage helper tracking articles saved today.
 *
 * Resets automatically at local-day rollover (same midnight boundary used by
 * the Morning Brief / useLocalMidnightInvalidation).
 */

const STORAGE_KEY = 'news.savedToday';

interface SavedTodayStore {
  date: string; // 'YYYY-MM-DD' in local time
  ids: string[];
}

/** Returns today's date as 'YYYY-MM-DD' using local wall-clock time. */
export function getTodayLocalDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function readStore(): SavedTodayStore {
  const today = getTodayLocalDate();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed: SavedTodayStore = JSON.parse(raw);
      if (parsed.date === today && Array.isArray(parsed.ids)) {
        return parsed;
      }
    }
  } catch {
    // private-mode or parse error — treat as empty
  }
  return { date: today, ids: [] };
}

function writeStore(store: SavedTodayStore): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // private-mode safety — silently ignore
  }
}

/**
 * Records that an article was saved today.
 * Deduplicates by id; resets the store if the stored date is not today.
 */
export function recordSavedToday(articleId: string): void {
  const store = readStore();
  if (!store.ids.includes(articleId)) {
    store.ids.push(articleId);
    writeStore(store);
  }
}

/**
 * Returns the number of articles saved today, or 0 if none / stale date.
 */
export function getSavedTodayCount(): number {
  return readStore().ids.length;
}
