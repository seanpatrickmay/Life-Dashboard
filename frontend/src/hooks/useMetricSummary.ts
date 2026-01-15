import { useQuery } from '@tanstack/react-query';

import { fetchReadinessSummary } from '../services/api';

export function useMetricSummary() {
  return useQuery({
    queryKey: ['readiness-summary'],
    queryFn: fetchReadinessSummary,
    staleTime: 1000 * 60 * 60
  });
}
