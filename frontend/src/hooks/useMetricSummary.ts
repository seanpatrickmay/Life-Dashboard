import { useQuery } from '@tanstack/react-query';

import { fetchReadinessSummary } from '../services/api';

export function useMetricSummary() {
  return useQuery({
    queryKey: ['readiness-summary'],
    queryFn: fetchReadinessSummary,
    refetchInterval: 1000 * 60 * 15
  });
}
