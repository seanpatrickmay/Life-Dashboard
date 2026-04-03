import { useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTopPerCategory,
  getAllByCategory,
  getCuratedFeed,
  refreshFeed,
  markArticleRead,
  getArticleById,
  extractKeywordsFromContext,
  hasArticles,
  type NewsArticle,
  type Category,
  type CuratedFeed,
} from '../services/newsFeedService';
import {
  recordRead,
  recordDismiss,
  saveArticle,
  unsaveArticle,
  dismissArticle,
  getSavedArticleIds,
  getCategoryDistribution,
  getExplorationSlots,
} from '../services/interestProfile';
import {
  scoreArticles,
  annotateArticles,
  summarizeProfile,
  type ArticleAnnotationResult,
} from '../services/api';
import {
  getProfileEmbedding,
  getArticleEmbeddings,
  cosineSimilarity,
} from '../services/profileSummarizer';
import { useTodos } from './useTodos';

const NEWS_FEED_KEY = ['news', 'feed'];
const NEWS_ALL_KEY = ['news', 'all'];
const NEWS_CURATED_KEY = ['news', 'curated'];
const NEWS_ANNOTATIONS_KEY = ['news', 'annotations'];
const PROFILE_SUMMARY_KEY = ['news', 'profile-summary'];

const PROFILE_CACHE_KEY = 'ld_profile_summary';
const PROFILE_CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 7 days

function loadCachedProfile(): { narrative: string; topics: string[] } | null {
  try {
    const raw = localStorage.getItem(PROFILE_CACHE_KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw);
    if (Date.now() - cached.timestamp > PROFILE_CACHE_TTL) return null;
    return cached;
  } catch { return null; }
}

function saveCachedProfile(narrative: string, topics: string[]): void {
  localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify({
    narrative,
    topics,
    timestamp: Date.now(),
  }));
}

export function useNewsFeed() {
  const queryClient = useQueryClient();
  const { todosQuery } = useTodos();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const getKeywords = useCallback((): string[] => {
    const todos = (todosQuery.data || [])
      .filter(t => !t.completed)
      .map(t => t.text);

    const projectsData = queryClient.getQueryData?.<any[]>(['projects']) || [];
    const projectNames = projectsData.map((p: any) => p.name || '').filter(Boolean);

    const calendarData = queryClient.getQueryData?.<any[]>(['calendar', 'events']) || [];
    const calendarTitles = calendarData.map((e: any) => e.summary || '').filter(Boolean);

    return extractKeywordsFromContext(todos, projectNames, calendarTitles);
  }, [todosQuery.data, queryClient]);

  // LLM profile summary (cached for 7 days)
  const profileQuery = useQuery<{ narrative: string; topics: string[] }>({
    queryKey: PROFILE_SUMMARY_KEY,
    queryFn: async () => {
      const cached = loadCachedProfile();
      if (cached) return cached;

      const projectsData = queryClient.getQueryData?.<any[]>(['projects']) || [];
      const projectNames = projectsData.map((p: any) => p.name || '').filter(Boolean);

      const todos = (todosQuery.data || [])
        .filter(t => !t.completed)
        .map(t => t.text)
        .slice(0, 20);

      const calendarData = queryClient.getQueryData?.<any[]>(['calendar', 'events']) || [];
      const calendarTitles = calendarData.map((e: any) => e.summary || '').filter(Boolean).slice(0, 10);

      const dist = getCategoryDistribution();
      const readingCategories: Record<string, number> = {};
      for (const [cat, proportion] of Object.entries(dist)) {
        readingCategories[cat] = Math.round(proportion * 100);
      }

      const result = await summarizeProfile({
        projects: projectNames,
        todos,
        calendar_events: calendarTitles,
        reading_categories: readingCategories,
      });

      if (result.narrative) {
        saveCachedProfile(result.narrative, result.topics);
      }
      return result;
    },
    staleTime: PROFILE_CACHE_TTL,
    refetchOnWindowFocus: false,
    retry: false,
  });

  // Dashboard: top article per category (legacy)
  const feedQuery = useQuery<NewsArticle[]>({
    queryKey: NEWS_FEED_KEY,
    queryFn: async () => {
      if (!hasArticles()) {
        const keywords = getKeywords();
        await refreshFeed(keywords);
      }
      return getTopPerCategory();
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  // News page: all articles by category (legacy)
  const allQuery = useQuery<Record<Category, NewsArticle[]>>({
    queryKey: NEWS_ALL_KEY,
    queryFn: async () => {
      if (!hasArticles()) {
        const keywords = getKeywords();
        await refreshFeed(keywords);
      }
      return getAllByCategory();
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  // Curated briefing
  const curatedQuery = useQuery<CuratedFeed>({
    queryKey: NEWS_CURATED_KEY,
    queryFn: async () => {
      if (!hasArticles()) {
        const keywords = getKeywords();
        await refreshFeed(keywords);
      }
      const curated = getCuratedFeed(getSavedArticleIds(), getExplorationSlots());

      // Apply LLM scoring as a multiplier if profile is available
      const profile = profileQuery.data;
      if (profile?.narrative) {
        try {
          const allArticles = [...curated.picks, ...curated.more];
          const scores = await scoreArticles(
            allArticles.map(a => ({
              id: a.id,
              title: a.title,
              summary: a.summary,
              category: a.category,
            })),
            profile.narrative,
          );

          if (scores.length > 0) {
            const scoreMap = new Map(scores.map(s => [s.id, s.score / 10])); // normalize 1-10 → 0.1-1.0
            const boosted = allArticles.map(a => {
              const llmScore = scoreMap.get(a.id);
              if (llmScore === undefined) return a;
              return {
                ...a,
                relevanceScore: a.relevanceScore * (0.7 + 0.3 * llmScore),
              };
            });

            boosted.sort((a, b) => b.relevanceScore - a.relevanceScore);
            curated.picks = boosted.slice(0, 8);
            curated.more = boosted.slice(8, 28);
          }
        } catch {
          // Graceful degradation: LLM scoring failed, use base scores
        }
      }

      // Apply embedding similarity as an additional boost
      try {
        const profileEmb = await getProfileEmbedding();
        if (profileEmb) {
          const allArticles = [...curated.picks, ...curated.more];
          const articleEmbs = await getArticleEmbeddings(allArticles);

          if (articleEmbs.size > 0) {
            const boosted = allArticles.map(a => {
              const emb = articleEmbs.get(a.id);
              if (!emb) return a;
              const sim = cosineSimilarity(profileEmb, emb);
              // Embedding similarity as a gentle boost: ±10% of base score
              return {
                ...a,
                relevanceScore: a.relevanceScore * (0.9 + 0.2 * sim),
              };
            });
            boosted.sort((a, b) => b.relevanceScore - a.relevanceScore);
            curated.picks = boosted.slice(0, 8);
            curated.more = boosted.slice(8, 28);
          }
        }
      } catch {
        // Graceful degradation: embeddings failed, use existing scores
      }

      return curated;
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  // Annotations for top picks (runs after curated query resolves)
  const annotationsQuery = useQuery<Record<string, string>>({
    queryKey: NEWS_ANNOTATIONS_KEY,
    queryFn: async () => {
      const profile = profileQuery.data;
      const picks = curatedQuery.data?.picks;
      if (!profile?.narrative || !picks?.length) return {};

      try {
        const results = await annotateArticles(
          picks.map(a => ({
            id: a.id,
            title: a.title,
            summary: a.summary,
            category: a.category,
          })),
          profile.narrative,
        );
        const map: Record<string, string> = {};
        for (const r of results) {
          map[r.id] = r.annotation;
        }
        return map;
      } catch {
        return {};
      }
    },
    enabled: !!profileQuery.data?.narrative && !!curatedQuery.data?.picks?.length,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: false,
  });

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: NEWS_FEED_KEY });
    queryClient.invalidateQueries({ queryKey: NEWS_ALL_KEY });
    queryClient.invalidateQueries({ queryKey: NEWS_CURATED_KEY });
    queryClient.invalidateQueries({ queryKey: NEWS_ANNOTATIONS_KEY });
  }, [queryClient]);

  const doRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const keywords = getKeywords();
      await refreshFeed(keywords);
      invalidateAll();
    } finally {
      setIsRefreshing(false);
    }
  }, [getKeywords, invalidateAll]);

  const markReadMutation = useMutation({
    mutationFn: async (articleId: string) => {
      markArticleRead(articleId);
      const article = getArticleById(articleId);
      if (article) {
        recordRead(article.category, article.sourceName);
      }
    },
    onSuccess: invalidateAll,
  });

  const saveMutation = useMutation({
    mutationFn: async (articleId: string) => {
      saveArticle(articleId);
    },
    onSuccess: invalidateAll,
  });

  const unsaveMutation = useMutation({
    mutationFn: async (articleId: string) => {
      unsaveArticle(articleId);
    },
    onSuccess: invalidateAll,
  });

  const dismissMutation = useMutation({
    mutationFn: async (articleId: string) => {
      const article = getArticleById(articleId);
      if (article) {
        recordDismiss(article.category, article.sourceName, articleId);
      } else {
        dismissArticle(articleId);
      }
    },
    onSuccess: invalidateAll,
  });

  return {
    feedQuery,
    allQuery,
    curatedQuery,
    annotationsQuery,
    profileQuery,
    refreshFeed: doRefresh,
    markRead: markReadMutation.mutate,
    saveArticle: saveMutation.mutate,
    unsaveArticle: unsaveMutation.mutate,
    dismissArticle: dismissMutation.mutate,
    isRefreshing,
  };
}
