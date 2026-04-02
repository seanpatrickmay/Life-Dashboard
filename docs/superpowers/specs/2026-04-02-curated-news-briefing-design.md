# Curated News Briefing — Design Spec

**Date:** 2026-04-02
**Status:** Approved (autonomous)

## Problem

The current news page surfaces ~119 articles per refresh across 7 categories with no meaningful curation. The keyword-matching scorer assigns 0.1 (baseline) to most articles since few match active todos. The result is a noisy, overwhelming firehose rather than a focused reading experience.

## Goals

1. **Fewer, better articles** — Show a curated briefing of 5-8 top picks, not 100+ undifferentiated articles
2. **Learn from behavior** — Track what the user reads and improve future picks automatically
3. **Encourage reading** — Editorial-style layout that creates hierarchy and makes articles inviting
4. **No backend changes** — All curation runs client-side (localStorage)

## Architecture

### Phase 1: Curation Engine

#### Interest Profile (`interestProfile.ts`)

New module that tracks user reading behavior in localStorage:

```typescript
type InterestProfile = {
  categoryAffinity: Record<string, { reads: number; lastReadAt: string }>;
  sourceAffinity: Record<string, { reads: number; lastReadAt: string }>;
  savedArticleIds: string[];
  totalReadsAllTime: number;
  updatedAt: string;
};
```

- `recordRead(article)` — Increments category + source affinity counts
- `getAffinityScore(category, source)` — Returns 0-1 score using exponential decay (7-day half-life) so recent reading patterns matter more than old ones
- `saveArticle(id)` / `unsaveArticle(id)` — Bookmark management
- Profile stored in `ld_interest_profile` localStorage key

#### Enhanced Scoring (refactored `scoreArticle`)

Replace the single keyword-match score with a multi-signal blend:

| Signal | Weight | Description |
|--------|--------|-------------|
| Keyword relevance | 0.25 | Existing todo keyword matching (preserved) |
| Interest affinity | 0.30 | User's category + source reading history |
| Recency | 0.20 | Exponential decay from publish time (12h half-life) |
| Source quality | 0.15 | Configurable source reputation tier |
| Diversity bonus | 0.10 | Boost for underrepresented categories in current picks |

Final score = weighted sum, clamped to [0.05, 1.0].

#### Topic Deduplication

Before final ranking, group articles by title similarity:
- Extract significant words (drop stopwords, words < 4 chars)
- Two articles are "similar" if they share > 50% of significant title words
- Keep highest-scored article per group, discard others

#### Curated Feed (`getCuratedFeed`)

New function that produces the briefing:
1. Score all unread articles with enhanced scoring
2. Deduplicate similar topics
3. Apply diversity constraints: max 2 articles from any single source
4. Return `{ picks: NewsArticle[] (top 8), more: NewsArticle[] (next 20) }`

#### Reduced Fetch Volume

- RSS: 8 items per feed (down from 12)
- "On This Day": 3 items (down from 4)
- Wikipedia Trending: 4 items (down from 6)
- Drops total from ~119 to ~83 articles per refresh

### Phase 2: Editorial UI

#### Layout (top to bottom)

1. **Header** — "Today's Briefing" + date + reading streak pill ("3 read today")
2. **Hero Card** — #1 pick, full-width, with visible summary, source, and time
3. **Picks Grid** — Next 4-7 picks in a responsive 2-column grid
4. **More Stories** — Expandable section with remaining articles as a compact list
5. **Saved** — Section showing bookmarked articles (if any exist)

#### Interactions

- Click article → open in new tab, mark read, update interest profile
- Bookmark icon on each card → save/unsave
- Dismiss (X) on each card → hide article
- No category tabs — curation IS the filtering
- Manual refresh button preserved

#### Visual Design

- Matches Monet aesthetic: soft shadows, rounded cards, halo text
- Hero card: larger title, summary visible, source pill with category color
- Pick cards: medium size, title + source + time
- More stories: compact rows, title + source only
- Reading progress pill: uses pond palette

### Files Changed

- `frontend/src/services/newsFeedService.ts` — Refactored scoring, reduced fetch limits, new `getCuratedFeed()`
- `frontend/src/services/interestProfile.ts` — New: interest tracking + affinity scoring
- `frontend/src/hooks/useNewsFeed.ts` — Add curated feed query, bookmark/dismiss mutations
- `frontend/src/pages/News.tsx` — Complete UI rewrite to editorial layout
- `frontend/src/components/dashboard/DashboardNewsFeed.tsx` — Minor: use curated picks instead of per-category

### Files NOT Changed

- Backend (`backend/`) — No changes
- Database schemas — No changes
- Other pages/components — No changes
