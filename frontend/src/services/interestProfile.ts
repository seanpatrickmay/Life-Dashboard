const PROFILE_KEY = 'ld_interest_profile';
const PROFILE_VERSION = 2;

type AffinityEntry = {
  reads: number;
  lastReadAt: string;
};

type AffinityLayer = {
  halfLifeDays: number;
  categoryAffinity: Record<string, AffinityEntry>;
  sourceAffinity: Record<string, AffinityEntry>;
};

type DismissRecord = {
  category: string;
  sourceName: string;
  articleId: string;
  dismissedAt: string;
};

export type InterestProfile = {
  version: number;
  ephemeral: AffinityLayer;
  contextual: AffinityLayer;
  stable: AffinityLayer;
  savedArticleIds: string[];
  dismissedArticleIds: string[];
  dismissHistory: DismissRecord[];
  totalReadsAllTime: number;
  updatedAt: string;
};

function emptyLayer(halfLife: number): AffinityLayer {
  return { halfLifeDays: halfLife, categoryAffinity: {}, sourceAffinity: {} };
}

function emptyProfile(): InterestProfile {
  return {
    version: PROFILE_VERSION,
    ephemeral: emptyLayer(3),
    contextual: emptyLayer(21),
    stable: emptyLayer(120),
    savedArticleIds: [],
    dismissedArticleIds: [],
    dismissHistory: [],
    totalReadsAllTime: 0,
    updatedAt: new Date().toISOString(),
  };
}

/** Migrate legacy single-tier profiles to three-tier structure. */
function migrateV1(legacy: any): InterestProfile {
  const profile = emptyProfile();
  if (legacy.categoryAffinity) {
    profile.contextual.categoryAffinity = legacy.categoryAffinity;
  }
  if (legacy.sourceAffinity) {
    profile.contextual.sourceAffinity = legacy.sourceAffinity;
  }
  profile.savedArticleIds = legacy.savedArticleIds || [];
  profile.dismissedArticleIds = legacy.dismissedArticleIds || [];
  profile.totalReadsAllTime = legacy.totalReadsAllTime || 0;
  return profile;
}

export function loadProfile(): InterestProfile {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.totalReadsAllTime === 'number') {
        if (!parsed.version || parsed.version < PROFILE_VERSION) {
          const migrated = migrateV1(parsed);
          saveProfile(migrated);
          return migrated;
        }
        return parsed;
      }
    }
  } catch { /* ignore */ }
  return emptyProfile();
}

function saveProfile(profile: InterestProfile): void {
  profile.updatedAt = new Date().toISOString();
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

function updateLayer(layer: AffinityLayer, category: string, sourceName: string, now: string): void {
  const cat = layer.categoryAffinity[category] || { reads: 0, lastReadAt: now };
  cat.reads += 1;
  cat.lastReadAt = now;
  layer.categoryAffinity[category] = cat;

  const src = layer.sourceAffinity[sourceName] || { reads: 0, lastReadAt: now };
  src.reads += 1;
  src.lastReadAt = now;
  layer.sourceAffinity[sourceName] = src;
}

export function recordRead(category: string, sourceName: string): void {
  const profile = loadProfile();
  const now = new Date().toISOString();

  updateLayer(profile.ephemeral, category, sourceName, now);
  updateLayer(profile.contextual, category, sourceName, now);
  updateLayer(profile.stable, category, sourceName, now);

  profile.totalReadsAllTime += 1;
  saveProfile(profile);
}

function layerDecayedScore(layer: AffinityLayer, category: string, sourceName: string): number {
  const now = Date.now();

  function decayed(entry: AffinityEntry | undefined, halfLife: number): number {
    if (!entry || entry.reads === 0) return 0;
    const daysSince = (now - new Date(entry.lastReadAt).getTime()) / (1000 * 60 * 60 * 24);
    const decay = Math.pow(0.5, daysSince / halfLife);
    return Math.min(entry.reads * decay, 10) / 10;
  }

  const catScore = decayed(layer.categoryAffinity[category], layer.halfLifeDays);
  const srcScore = decayed(layer.sourceAffinity[sourceName], layer.halfLifeDays);
  return 0.6 * catScore + 0.4 * srcScore;
}

/**
 * Compute a 0-1 affinity score blending all three temporal layers.
 * Blend: 50% ephemeral + 30% contextual + 20% stable
 */
export function getAffinityScore(category: string, sourceName: string): number {
  const profile = loadProfile();
  if (profile.totalReadsAllTime === 0) return 0.5;

  const ephScore = layerDecayedScore(profile.ephemeral, category, sourceName);
  const ctxScore = layerDecayedScore(profile.contextual, category, sourceName);
  const stbScore = layerDecayedScore(profile.stable, category, sourceName);

  return 0.5 * ephScore + 0.3 * ctxScore + 0.2 * stbScore;
}

export function recordDismiss(category: string, sourceName: string, articleId: string): void {
  const profile = loadProfile();
  if (!profile.dismissedArticleIds.includes(articleId)) {
    profile.dismissedArticleIds.push(articleId);
    if (profile.dismissedArticleIds.length > 200) {
      profile.dismissedArticleIds = profile.dismissedArticleIds.slice(-200);
    }
  }
  profile.dismissHistory.push({
    category,
    sourceName,
    articleId,
    dismissedAt: new Date().toISOString(),
  });
  if (profile.dismissHistory.length > 500) {
    profile.dismissHistory = profile.dismissHistory.slice(-500);
  }
  saveProfile(profile);
}

/**
 * Get negative penalty for a category from dismiss history.
 * Only penalizes within the same category. Source match adds extra weight.
 * Returns a negative number (0 to -1). Uses 30-day decay.
 */
export function getDismissPenalty(category: string, sourceName: string): number {
  const profile = loadProfile();
  const now = Date.now();
  const DISMISS_HALF_LIFE = 30;

  let penalty = 0;
  for (const d of profile.dismissHistory) {
    if (d.category !== category) continue;
    const daysSince = (now - new Date(d.dismissedAt).getTime()) / (1000 * 60 * 60 * 24);
    const decay = Math.pow(0.5, daysSince / DISMISS_HALF_LIFE);
    const weight = d.sourceName === sourceName ? -1.0 : -0.6;
    penalty += weight * decay;
  }

  return Math.max(penalty, -1.0);
}

/**
 * Get the top N categories by total reads.
 * Uses the stable layer only to avoid triple-counting.
 */
export function getTopCategories(n: number): string[] {
  const profile = loadProfile();
  const totals: Record<string, number> = {};

  for (const [cat, entry] of Object.entries(profile.stable.categoryAffinity)) {
    totals[cat] = (totals[cat] || 0) + entry.reads;
  }

  return Object.entries(totals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([cat]) => cat);
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
 * Uses stable layer reads normalized by totalReadsAllTime.
 */
export function getCategoryDistribution(): Record<string, number> {
  const profile = loadProfile();
  const total = profile.totalReadsAllTime || 1;
  const dist: Record<string, number> = {};
  for (const [cat, entry] of Object.entries(profile.stable.categoryAffinity)) {
    dist[cat] = entry.reads / total;
  }
  return dist;
}
