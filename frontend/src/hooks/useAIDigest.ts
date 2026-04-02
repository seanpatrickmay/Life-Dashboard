import { useCallback, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchDigest, refreshDigest, type DigestResponse } from '../services/api';

const AI_DIGEST_KEY = ['ai-digest'];

export function useAIDigest() {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const digestQuery = useQuery<DigestResponse>({
    queryKey: AI_DIGEST_KEY,
    queryFn: fetchDigest,
    staleTime: 1000 * 60 * 60,
    refetchOnWindowFocus: false,
  });

  const doRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await refreshDigest();
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: AI_DIGEST_KEY });
        setIsRefreshing(false);
      }, 3000);
    } catch {
      setIsRefreshing(false);
    }
  }, [queryClient]);

  return {
    digestQuery,
    refreshDigest: doRefresh,
    isRefreshing,
  };
}
