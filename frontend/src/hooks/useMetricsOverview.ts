import { useQuery } from '@tanstack/react-query';

import { fetchMetricsOverview } from '../services/api';

export function useMetricsOverview(rangeDays = 14) {
  return useQuery({
    queryKey: ['metrics-overview', rangeDays],
    queryFn: () => fetchMetricsOverview(rangeDays),
    staleTime: 1000 * 60 * 5
  });
}
