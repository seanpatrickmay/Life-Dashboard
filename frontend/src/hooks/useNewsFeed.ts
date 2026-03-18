import { useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getUnsurfacedArticles,
  refreshFeed,
  markArticleRead,
  extractKeywordsFromContext,
  hasArticles,
  type NewsArticle,
} from '../services/newsFeedService';
import { useTodos } from './useTodos';

const NEWS_FEED_KEY = ['news', 'feed'];

export function useNewsFeed() {
  const queryClient = useQueryClient();
  const { todosQuery } = useTodos();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const getKeywords = useCallback((): string[] => {
    const todos = (todosQuery.data || [])
      .filter(t => !t.completed)
      .map(t => t.text);
    // Projects are not directly available here, but todos give us good signal
    return extractKeywordsFromContext(todos, []);
  }, [todosQuery.data]);

  const feedQuery = useQuery<NewsArticle[]>({
    queryKey: NEWS_FEED_KEY,
    queryFn: async () => {
      // If no articles available, do an initial refresh
      if (!hasArticles()) {
        const keywords = getKeywords();
        await refreshFeed(keywords);
      }
      return getUnsurfacedArticles(8);
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
    } finally {
      setIsRefreshing(false);
    }
  }, [getKeywords, queryClient]);

  const markReadMutation = useMutation({
    mutationFn: async (articleId: string) => {
      markArticleRead(articleId);
    },
  });

  return {
    feedQuery,
    refreshFeed: doRefresh,
    markRead: markReadMutation.mutate,
    isRefreshing,
  };
}
