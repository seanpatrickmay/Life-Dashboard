import { useQuery } from '@tanstack/react-query';

import { fetchInsight } from '../services/api';

export function useInsight() {
  return useQuery({
    queryKey: ['insight'],
    queryFn: fetchInsight,
    staleTime: 1000 * 60 * 60
  });
}
