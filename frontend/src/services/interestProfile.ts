const PROFILE_KEY = 'ld_interest_profile';
const HALF_LIFE_DAYS = 7;

type AffinityEntry = {
  reads: number;
  lastReadAt: string;
};

export type InterestProfile = {
  categoryAffinity: Record<string, AffinityEntry>;
  sourceAffinity: Record<string, AffinityEntry>;
  savedArticleIds: string[];
  dismissedArticleIds: string[];
  totalReadsAllTime: number;
  updatedAt: string;
};

function emptyProfile(): InterestProfile {
  return {
    categoryAffinity: {},
    sourceAffinity: {},
    savedArticleIds: [],
    dismissedArticleIds: [],
    totalReadsAllTime: 0,
    updatedAt: new Date().toISOString(),
  };
}

export function loadProfile(): InterestProfile {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.totalReadsAllTime === 'number') return parsed;
    }
  } catch { /* ignore */ }
  return emptyProfile();
}

function saveProfile(profile: InterestProfile): void {
  profile.updatedAt = new Date().toISOString();
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

export function recordRead(category: string, sourceName: string): void {
  const profile = loadProfile();
  const now = new Date().toISOString();

  const cat = profile.categoryAffinity[category] || { reads: 0, lastReadAt: now };
  cat.reads += 1;
  cat.lastReadAt = now;
  profile.categoryAffinity[category] = cat;

  const src = profile.sourceAffinity[sourceName] || { reads: 0, lastReadAt: now };
  src.reads += 1;
  src.lastReadAt = now;
  profile.sourceAffinity[sourceName] = src;

  profile.totalReadsAllTime += 1;
  saveProfile(profile);
}

/**
 * Compute a 0–1 affinity score for a category + source pair.
 * Uses exponential decay so recent reads matter more.
 */
export function getAffinityScore(category: string, sourceName: string): number {
  const profile = loadProfile();
  if (profile.totalReadsAllTime === 0) return 0.5; // neutral when no history

  const now = Date.now();

  function decayedScore(entry: AffinityEntry | undefined): number {
    if (!entry || entry.reads === 0) return 0;
    const daysSince = (now - new Date(entry.lastReadAt).getTime()) / (1000 * 60 * 60 * 24);
    const decay = Math.pow(0.5, daysSince / HALF_LIFE_DAYS);
    return Math.min(entry.reads * decay, 10) / 10; // cap at 1.0
  }

  const catScore = decayedScore(profile.categoryAffinity[category]);
  const srcScore = decayedScore(profile.sourceAffinity[sourceName]);

  // Blend: 60% category, 40% source
  return 0.6 * catScore + 0.4 * srcScore;
}

export function saveArticle(articleId: string): void {
  const profile = loadProfile();
  if (!profile.savedArticleIds.includes(articleId)) {
    profile.savedArticleIds.push(articleId);
    saveProfile(profile);
  }
}

export function unsaveArticle(articleId: string): void {
  const profile = loadProfile();
  profile.savedArticleIds = profile.savedArticleIds.filter(id => id !== articleId);
  saveProfile(profile);
}

export function isArticleSaved(articleId: string): boolean {
  return loadProfile().savedArticleIds.includes(articleId);
}

export function getSavedArticleIds(): string[] {
  return loadProfile().savedArticleIds;
}

export function dismissArticle(articleId: string): void {
  const profile = loadProfile();
  if (!profile.dismissedArticleIds.includes(articleId)) {
    profile.dismissedArticleIds.push(articleId);
    // Cap dismissed list at 200 to prevent unbounded growth
    if (profile.dismissedArticleIds.length > 200) {
      profile.dismissedArticleIds = profile.dismissedArticleIds.slice(-200);
    }
    saveProfile(profile);
  }
}

export function isDismissed(articleId: string): boolean {
  return loadProfile().dismissedArticleIds.includes(articleId);
}

/**
 * Get the category distribution of reading history for diversity calculations.
 * Returns a map of category → proportion of total reads (0–1).
 */
export function getCategoryDistribution(): Record<string, number> {
  const profile = loadProfile();
  const total = profile.totalReadsAllTime || 1;
  const dist: Record<string, number> = {};
  for (const [cat, entry] of Object.entries(profile.categoryAffinity)) {
    dist[cat] = entry.reads / total;
  }
  return dist;
}
