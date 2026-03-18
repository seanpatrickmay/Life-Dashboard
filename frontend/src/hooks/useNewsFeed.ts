import { useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTopPerCategory,
  getAllByCategory,
  refreshFeed,
  markArticleRead,
  extractKeywordsFromContext,
  hasArticles,
  type NewsArticle,
  type Category,
} from '../services/newsFeedService';
import { useTodos } from './useTodos';

const NEWS_FEED_KEY = ['news', 'feed'];
const NEWS_ALL_KEY = ['news', 'all'];

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

  // Dashboard: top article per category
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

  // News page: all articles by category
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

  const doRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const keywords = getKeywords();
      await refreshFeed(keywords);
      queryClient.invalidateQueries({ queryKey: NEWS_FEED_KEY });
      queryClient.invalidateQueries({ queryKey: NEWS_ALL_KEY });
    } finally {
      setIsRefreshing(false);
    }
  }, [getKeywords, queryClient]);

  const markReadMutation = useMutation({
    mutationFn: async (articleId: string) => {
      markArticleRead(articleId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NEWS_FEED_KEY });
      queryClient.invalidateQueries({ queryKey: NEWS_ALL_KEY });
    },
  });

  return {
    feedQuery,
    allQuery,
    refreshFeed: doRefresh,
    markRead: markReadMutation.mutate,
    isRefreshing,
  };
}
