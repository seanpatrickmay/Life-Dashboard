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
  saveArticle,
  unsaveArticle,
  dismissArticle,
  getSavedArticleIds,
} from '../services/interestProfile';
import { useTodos } from './useTodos';

const NEWS_FEED_KEY = ['news', 'feed'];
const NEWS_ALL_KEY = ['news', 'all'];
const NEWS_CURATED_KEY = ['news', 'curated'];

export function useNewsFeed() {
  const queryClient = useQueryClient();
  const { todosQuery } = useTodos();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const getKeywords = useCallback((): string[] => {
    const todos = (todosQuery.data || [])
      .filter(t => !t.completed)
      .map(t => t.text);
    return extractKeywordsFromContext(todos, []);
  }, [todosQuery.data]);

  // Dashboard: top article per category (legacy, still used by dashboard widget)
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

  // News page: all articles by category (legacy, kept for backward compat)
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

  // Curated briefing for the revamped news page
  const curatedQuery = useQuery<CuratedFeed>({
    queryKey: NEWS_CURATED_KEY,
    queryFn: async () => {
      if (!hasArticles()) {
        const keywords = getKeywords();
        await refreshFeed(keywords);
      }
      return getCuratedFeed(getSavedArticleIds());
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: NEWS_FEED_KEY });
    queryClient.invalidateQueries({ queryKey: NEWS_ALL_KEY });
    queryClient.invalidateQueries({ queryKey: NEWS_CURATED_KEY });
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
      // Update interest profile with this read
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
      dismissArticle(articleId);
    },
    onSuccess: invalidateAll,
  });

  return {
    feedQuery,
    allQuery,
    curatedQuery,
    refreshFeed: doRefresh,
    markRead: markReadMutation.mutate,
    saveArticle: saveMutation.mutate,
    unsaveArticle: unsaveMutation.mutate,
    dismissArticle: dismissMutation.mutate,
    isRefreshing,
  };
}
