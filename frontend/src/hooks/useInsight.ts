import { useQuery } from '@tanstack/react-query';

import { fetchInsight } from '../services/api';

export function useInsight() {
  return useQuery({
    queryKey: ['insight'],
    queryFn: fetchInsight,
    refetchInterval: 1000 * 60 * 15
  });
}
