# Phase 1: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single 7-day interest decay with a three-tier model, expand keyword extraction, implement 50% exploration slots, fix UI accessibility issues, and add 3 new RSS sources.

**Architecture:** All changes are frontend-only (localStorage + React). The interest profile gets a new three-tier structure with localStorage migration. The scoring formula gains negative penalties and exploration slots. UI fixes are CSS-only changes to font sizes and touch targets.

**Tech Stack:** React 18, TypeScript, styled-components, Vitest, localStorage

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/services/interestProfile.ts` | Modify | Three-tier decay model, dismiss tracking with negative penalties, localStorage migration |
| `frontend/src/services/newsFeedService.ts` | Modify | New sources, SOURCE_QUALITY entries, exploration slots in getCuratedFeed, expanded extractKeywordsFromContext |
| `frontend/src/hooks/useNewsFeed.ts` | Modify | Pass calendar/journal data to keyword extraction |
| `frontend/src/pages/News.tsx` | Modify | Font size fixes, touch target fixes |
| `frontend/src/services/newsFeedService.test.ts` | Modify | Tests for exploration slots, new scoring |
| `frontend/src/services/interestProfile.test.ts` | Create | Tests for three-tier decay, migration, dismiss penalties |

---

### Task 1: Three-Tier Interest Profile

**Files:**
- Create: `frontend/src/services/interestProfile.test.ts`
- Modify: `frontend/src/services/interestProfile.ts`

- [ ] **Step 1: Write failing tests for the new profile structure**

```typescript
// @vitest-environment jsdom
import { describe, expect, it, beforeEach } from 'vitest';
import {
  loadProfile,
  recordRead,
  getAffinityScore,
  recordDismiss,
  getDismissPenalty,
  getTopCategories,
} from './interestProfile';

const PROFILE_KEY = 'ld_interest_profile';

beforeEach(() => { localStorage.clear(); });

describe('three-tier profile', () => {
  it('creates empty profile with ephemeral, contextual, and stable layers', () => {
    const profile = loadProfile();
    expect(profile.ephemeral).toBeDefined();
    expect(profile.contextual).toBeDefined();
    expect(profile.stable).toBeDefined();
    expect(profile.ephemeral.halfLifeDays).toBe(3);
    expect(profile.contextual.halfLifeDays).toBe(21);
    expect(profile.stable.halfLifeDays).toBe(120);
  });

  it('recordRead updates ephemeral layer', () => {
    recordRead('tech', 'Hacker News');
    const profile = loadProfile();
    expect(profile.ephemeral.categoryAffinity['tech']?.reads).toBe(1);
  });

  it('getAffinityScore blends all three layers', () => {
    recordRead('tech', 'Hacker News');
    const score = getAffinityScore('tech', 'Hacker News');
    expect(score).toBeGreaterThan(0);
    expect(score).toBeLessThanOrEqual(1);
  });

  it('migrates legacy single-tier profiles on load', () => {
    // Seed old-format profile
    localStorage.setItem(PROFILE_KEY, JSON.stringify({
      categoryAffinity: { tech: { reads: 5, lastReadAt: new Date().toISOString() } },
      sourceAffinity: { 'HN': { reads: 3, lastReadAt: new Date().toISOString() } },
      savedArticleIds: ['a1'],
      dismissedArticleIds: ['d1'],
      totalReadsAllTime: 5,
      updatedAt: new Date().toISOString(),
    }));
    const profile = loadProfile();
    // Old data should migrate into contextual layer
    expect(profile.contextual.categoryAffinity['tech']?.reads).toBe(5);
    expect(profile.savedArticleIds).toContain('a1');
  });
});

describe('dismiss penalties', () => {
  it('recordDismiss stores category and source penalty', () => {
    recordDismiss('tech', 'Hacker News', 'article-1');
    const penalty = getDismissPenalty('tech', 'Hacker News');
    expect(penalty).toBeLessThan(0);
  });

  it('dismiss penalty decays over 30 days', () => {
    // Record a dismiss 31 days ago
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
    expect(Math.abs(penalty)).toBeLessThan(0.1); // Nearly fully decayed
  });
});

describe('getTopCategories', () => {
  it('returns top N categories by total reads', () => {
    recordRead('tech', 'HN');
    recordRead('tech', 'HN');
    recordRead('tech', 'HN');
    recordRead('science', 'Nature');
    recordRead('science', 'Nature');
    recordRead('world', 'BBC');
    const top = getTopCategories(2);
    expect(top).toEqual(['tech', 'science']);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/services/interestProfile.test.ts`
Expected: FAIL — functions not yet updated

- [ ] **Step 3: Implement three-tier profile with migration**

Rewrite `interestProfile.ts` with the new type structure:

```typescript
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
  // Move old affinity data into contextual layer (medium-term)
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
        // Check if it's a legacy v1 profile (no version field or version < 2)
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

export function recordRead(category: string, sourceName: string): void {
  const profile = loadProfile();
  const now = new Date().toISOString();

  // Update ephemeral layer (short-term signal)
  const eCat = profile.ephemeral.categoryAffinity[category] || { reads: 0, lastReadAt: now };
  eCat.reads += 1;
  eCat.lastReadAt = now;
  profile.ephemeral.categoryAffinity[category] = eCat;

  const eSrc = profile.ephemeral.sourceAffinity[sourceName] || { reads: 0, lastReadAt: now };
  eSrc.reads += 1;
  eSrc.lastReadAt = now;
  profile.ephemeral.sourceAffinity[sourceName] = eSrc;

  // Update contextual layer (medium-term)
  const cCat = profile.contextual.categoryAffinity[category] || { reads: 0, lastReadAt: now };
  cCat.reads += 1;
  cCat.lastReadAt = now;
  profile.contextual.categoryAffinity[category] = cCat;

  const cSrc = profile.contextual.sourceAffinity[sourceName] || { reads: 0, lastReadAt: now };
  cSrc.reads += 1;
  cSrc.lastReadAt = now;
  profile.contextual.sourceAffinity[sourceName] = cSrc;

  // Update stable layer (long-term)
  const sCat = profile.stable.categoryAffinity[category] || { reads: 0, lastReadAt: now };
  sCat.reads += 1;
  sCat.lastReadAt = now;
  profile.stable.categoryAffinity[category] = sCat;

  const sSrc = profile.stable.sourceAffinity[sourceName] || { reads: 0, lastReadAt: now };
  sSrc.reads += 1;
  sSrc.lastReadAt = now;
  profile.stable.sourceAffinity[sourceName] = sSrc;

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
  // Cap dismiss history at 500
  if (profile.dismissHistory.length > 500) {
    profile.dismissHistory = profile.dismissHistory.slice(-500);
  }
  saveProfile(profile);
}

/**
 * Get negative penalty for a category+source from dismiss history.
 * Returns a negative number (0 to -1). Uses 30-day decay.
 */
export function getDismissPenalty(category: string, sourceName: string): number {
  const profile = loadProfile();
  const now = Date.now();
  const DISMISS_HALF_LIFE = 30;

  let penalty = 0;
  for (const d of profile.dismissHistory) {
    if (d.category !== category && d.sourceName !== sourceName) continue;
    const daysSince = (now - new Date(d.dismissedAt).getTime()) / (1000 * 60 * 60 * 24);
    const decay = Math.pow(0.5, daysSince / DISMISS_HALF_LIFE);
    const weight = d.category === category && d.sourceName === sourceName ? -1.0 :
                   d.category === category ? -0.6 : -0.4;
    penalty += weight * decay;
  }

  return Math.max(penalty, -1.0);
}

/** Get the top N categories by total reads across all layers. */
export function getTopCategories(n: number): string[] {
  const profile = loadProfile();
  const totals: Record<string, number> = {};

  for (const layer of [profile.ephemeral, profile.contextual, profile.stable]) {
    for (const [cat, entry] of Object.entries(layer.categoryAffinity)) {
      totals[cat] = (totals[cat] || 0) + entry.reads;
    }
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
  // Legacy function — now delegates to recordDismiss when category/source available
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

export function getCategoryDistribution(): Record<string, number> {
  const profile = loadProfile();
  const total = profile.totalReadsAllTime || 1;
  const dist: Record<string, number> = {};
  // Aggregate across all layers
  for (const layer of [profile.ephemeral, profile.contextual, profile.stable]) {
    for (const [cat, entry] of Object.entries(layer.categoryAffinity)) {
      dist[cat] = (dist[cat] || 0) + entry.reads;
    }
  }
  // Normalize — divide by total * 3 since each read increments all 3 layers
  for (const cat of Object.keys(dist)) {
    dist[cat] = dist[cat] / (total * 3);
  }
  return dist;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/services/interestProfile.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/interestProfile.ts frontend/src/services/interestProfile.test.ts
git commit -m "feat: replace single 7-day decay with three-tier interest profile

Three temporal layers:
- Ephemeral (3-day half-life): current reading
- Contextual (21-day): active project topics
- Stable (120-day): enduring interests

Includes localStorage migration from v1 profiles and dismiss
penalty tracking with 30-day decay."
```

---

### Task 2: New RSS Sources + Exploration Slots

**Files:**
- Modify: `frontend/src/services/newsFeedService.ts`
- Modify: `frontend/src/services/newsFeedService.test.ts`

- [ ] **Step 1: Write failing tests for exploration slots**

Add to `newsFeedService.test.ts`:

```typescript
import { getCuratedFeed, scoreArticle } from './newsFeedService';
import * as interestProfile from './interestProfile';

describe('getCuratedFeed exploration slots', () => {
  beforeEach(() => {
    localStorage.clear();
    // Seed reading history to establish top categories
    interestProfile.recordRead('tech', 'HN');
    interestProfile.recordRead('tech', 'HN');
    interestProfile.recordRead('tech', 'HN');
    interestProfile.recordRead('science', 'Nature');
    interestProfile.recordRead('science', 'Nature');
  });

  it('reserves exploration slots for underrepresented categories', () => {
    // Seed articles: 6 tech, 2 science, 2 world, 2 culture
    const articles = [
      ...Array.from({ length: 6 }, (_, i) => makeArticle({
        id: `tech-${i}`, category: 'tech', sourceName: `Source${i}`,
        relevanceScore: 0.9 - i * 0.05,
      })),
      ...Array.from({ length: 2 }, (_, i) => makeArticle({
        id: `sci-${i}`, category: 'science', sourceName: `SciSource${i}`,
        relevanceScore: 0.6,
      })),
      ...Array.from({ length: 2 }, (_, i) => makeArticle({
        id: `world-${i}`, category: 'world', sourceName: `WorldSource${i}`,
        relevanceScore: 0.5,
      })),
      ...Array.from({ length: 2 }, (_, i) => makeArticle({
        id: `culture-${i}`, category: 'culture', sourceName: `CultureSource${i}`,
        relevanceScore: 0.4,
      })),
    ];
    seedStorage(articles, new Date().toISOString());

    const curated = getCuratedFeed([], 4); // 4 exploration slots
    // Should have 8 picks total
    expect(curated.picks.length).toBe(8);
    // At least some picks should be from non-top categories
    const explorationPicks = curated.picks.filter(p => p.isExploration);
    expect(explorationPicks.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/services/newsFeedService.test.ts`
Expected: FAIL — `isExploration` field doesn't exist, `getCuratedFeed` doesn't accept exploration parameter

- [ ] **Step 3: Add new sources, update scoring, implement exploration slots**

In `newsFeedService.ts`:

1. Add 3 new RSS sources to `DEFAULT_SOURCES`:
```typescript
{ url: 'https://www.technologyreview.com/topic/artificial-intelligence/feed', name: 'MIT Tech Review AI', category: 'tech', enabled: true },
{ url: 'https://www.carbonbrief.org/feed', name: 'Carbon Brief', category: 'science', enabled: true },
{ url: 'https://aeon.co/feed.rss', name: 'Aeon', category: 'culture', enabled: true },
```

2. Add quality tiers:
```typescript
'MIT Tech Review AI': 0.85,
'Carbon Brief': 0.85,
'Aeon': 0.8,
```

3. Add `isExploration` to `NewsArticle` type:
```typescript
isExploration?: boolean;
```

4. Import `getDismissPenalty` and `getTopCategories` from interestProfile

5. Update `scoreArticle` to include negative penalty:
```typescript
export function scoreArticle(
  article: { title: string; summary: string | null; category: string; sourceName: string; publishedAt: string | null; fetchedAt: string },
  keywords: string[],
  categoryDistribution?: Record<string, number>,
): number {
  const kw = keywordRelevance(article, keywords);
  const affinity = getAffinityScore(article.category, article.sourceName);
  const recency = recencyScore(article.publishedAt, article.fetchedAt);
  const quality = sourceQualityScore(article.sourceName);
  const penalty = getDismissPenalty(article.category, article.sourceName);

  let diversity = 0.5;
  if (categoryDistribution) {
    const catProportion = categoryDistribution[article.category] ?? 0;
    diversity = 1.0 - catProportion;
  }

  const score =
    0.25 * kw +
    0.25 * affinity +
    0.25 * recency +
    0.15 * quality +
    0.10 * diversity +
    0.25 * penalty; // penalty is negative, reduces score

  return Math.max(0.05, Math.min(score, 1.0));
}
```

6. Rewrite `getCuratedFeed` with exploration slots:
```typescript
export function getCuratedFeed(savedIds: string[], explorationSlots = 4): CuratedFeed {
  const state = loadState();

  const savedSet = new Set(savedIds);
  const saved = state.articles.filter(a => savedSet.has(a.id));

  const candidates = state.articles
    .filter(a => !a.readAt && !isDismissed(a.id))
    .sort((a, b) => b.relevanceScore - a.relevanceScore || b.fetchedAt.localeCompare(a.fetchedAt));

  const deduped = deduplicateByTopic(candidates);

  // Source diversity: max 2 from any single source
  const diversified: NewsArticle[] = [];
  const sourceCount: Record<string, number> = {};
  for (const article of deduped) {
    const count = sourceCount[article.sourceName] || 0;
    if (count >= 2) continue;
    diversified.push(article);
    sourceCount[article.sourceName] = count + 1;
  }

  // Split into main picks and exploration picks
  const mainCount = 8 - explorationSlots;
  const topCategories = getTopCategories(3);

  const mainPicks = diversified
    .slice(0, mainCount);

  const explorationPool = diversified
    .filter(a => !topCategories.includes(a.category))
    .filter(a => !mainPicks.includes(a));

  const explorationPicks = explorationPool
    .slice(0, explorationSlots)
    .map(a => ({ ...a, isExploration: true }));

  const picks = [...mainPicks, ...explorationPicks];
  const picksSet = new Set(picks.map(a => a.id));
  const more = diversified.filter(a => !picksSet.has(a.id)).slice(0, 20);

  return { picks, more, saved };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/services/newsFeedService.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/newsFeedService.ts frontend/src/services/newsFeedService.test.ts
git commit -m "feat: add 3 RSS sources, exploration slots, and dismiss penalties

New sources: MIT Tech Review AI, Carbon Brief, Aeon
50% exploration (4 of 8 picks from underrepresented categories)
Dismiss penalty with 30-day decay integrated into scoring"
```

---

### Task 3: Expand Keyword Extraction

**Files:**
- Modify: `frontend/src/hooks/useNewsFeed.ts`
- Modify: `frontend/src/services/newsFeedService.ts`

- [ ] **Step 1: Update extractKeywordsFromContext to accept calendar and journal data**

In `newsFeedService.ts`, update the function signature and add new parameters:

```typescript
export function extractKeywordsFromContext(
  todos: string[],
  projects: string[],
  calendarEvents: string[] = [],
  journalThemes: string[] = [],
): string[] {
  const allText = [...todos, ...projects, ...calendarEvents, ...journalThemes]
    .join(' ').toLowerCase();
  // ... rest unchanged
}
```

- [ ] **Step 2: Update useNewsFeed to pass calendar events and journal themes**

In `useNewsFeed.ts`, import calendar and journal hooks and pass their data:

```typescript
const getKeywords = useCallback((): string[] => {
  const todos = (todosQuery.data || [])
    .filter(t => !t.completed)
    .map(t => t.text);

  // Pull project names from query cache if available
  const projectsData = queryClient.getQueryData<any[]>(['projects']) || [];
  const projectNames = projectsData.map((p: any) => p.name || '').filter(Boolean);

  // Pull calendar event titles from query cache if available
  const calendarData = queryClient.getQueryData<any[]>(['calendar', 'events']) || [];
  const calendarTitles = calendarData.map((e: any) => e.summary || '').filter(Boolean);

  return extractKeywordsFromContext(todos, projectNames, calendarTitles);
}, [todosQuery.data, queryClient]);
```

- [ ] **Step 3: Run existing tests to ensure nothing breaks**

Run: `cd frontend && npx vitest run`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useNewsFeed.ts frontend/src/services/newsFeedService.ts
git commit -m "feat: expand keyword extraction to include projects and calendar events"
```

---

### Task 4: UI Accessibility Fixes

**Files:**
- Modify: `frontend/src/pages/News.tsx`

- [ ] **Step 1: Fix metadata font sizes**

Update these styled components in `News.tsx`:

```
SourcePill: font-size 0.58rem → 0.75rem
HeroTimeAgo: font-size 0.58rem → 0.875rem
PickSource: font-size 0.58rem → 0.875rem
PickTimeAgo: font-size 0.55rem → 0.875rem
```

- [ ] **Step 2: Fix touch targets**

Update `IconButton` padding from `3px 6px` to `10px 12px` and add minimum dimensions:

```css
padding: 10px 12px;
min-width: 44px;
min-height: 44px;
display: inline-flex;
align-items: center;
justify-content: center;
```

Also remove the inline `style` overrides on the pick card IconButtons that reduce padding further.

- [ ] **Step 3: Add Discovery label for exploration picks**

Add a styled component and conditional rendering:

```typescript
const DiscoveryLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 5px;
  background: ${({ theme }) => theme.palette?.lilac?.['100'] ?? '#E5E0FF'}33;
  color: ${({ theme }) => theme.palette?.lilac?.['200'] ?? '#B1A7FF'};
  white-space: nowrap;
`;
```

In the picks grid, after the category Dot:
```tsx
{article.isExploration && <DiscoveryLabel>Discovery</DiscoveryLabel>}
```

- [ ] **Step 4: Run vitest to ensure nothing breaks**

Run: `cd frontend && npx vitest run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/News.tsx
git commit -m "fix: increase metadata font sizes to 14px and touch targets to 44px

Addresses WCAG accessibility: PickSource, PickTimeAgo, HeroTimeAgo,
SourcePill all raised from ~9px to 12-14px. IconButton touch targets
expanded from 20x18px to 44x44px minimum. Discovery label added for
exploration picks."
```

---

### Task 5: Update DashboardNewsFeed + useNewsFeed Integration

**Files:**
- Modify: `frontend/src/components/dashboard/DashboardNewsFeed.tsx`
- Modify: `frontend/src/hooks/useNewsFeed.ts`

- [ ] **Step 1: Update useNewsFeed dismiss mutation to use recordDismiss**

In `useNewsFeed.ts`, update the dismiss mutation to pass category and source:

```typescript
import {
  recordRead,
  recordDismiss,
  saveArticle,
  unsaveArticle,
  dismissArticle,
  getSavedArticleIds,
} from '../services/interestProfile';

// In the dismiss mutation:
const dismissMutation = useMutation({
  mutationFn: async (articleId: string) => {
    const article = getArticleById(articleId);
    if (article) {
      recordDismiss(article.category, article.sourceName, articleId);
    } else {
      dismissArticle(articleId); // fallback to legacy
    }
  },
  onSuccess: invalidateAll,
});
```

- [ ] **Step 2: Pass explorationSlots to getCuratedFeed**

In the curated query:

```typescript
const curatedQuery = useQuery<CuratedFeed>({
  queryKey: NEWS_CURATED_KEY,
  queryFn: async () => {
    if (!hasArticles()) {
      const keywords = getKeywords();
      await refreshFeed(keywords);
    }
    return getCuratedFeed(getSavedArticleIds(), 4); // 50% exploration
  },
  staleTime: 5 * 60 * 1000,
  refetchOnWindowFocus: false,
});
```

- [ ] **Step 3: Run all tests**

Run: `cd frontend && npx vitest run`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useNewsFeed.ts frontend/src/components/dashboard/DashboardNewsFeed.tsx
git commit -m "feat: integrate dismiss tracking and exploration slots into news hooks"
```

---

### Task 6: Final Integration Test + Cleanup

- [ ] **Step 1: Run full test suite**

Run: `cd frontend && npx vitest run`
Expected: All tests PASS

- [ ] **Step 2: Run typecheck if available**

Run: `cd frontend && npx tsc --noEmit 2>/dev/null || echo 'no tsconfig strict checking'`

- [ ] **Step 3: Verify dev server starts**

Run: `cd frontend && timeout 15 npm run dev 2>&1 | head -20`
Expected: Server starts without errors

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: Phase 1 cleanup and integration verification"
```
