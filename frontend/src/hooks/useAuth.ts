import { useQuery } from '@tanstack/react-query';
import { fetchAuthMe, type AuthMeResponse } from '../services/api';

export function useAuth() {
  return useQuery<AuthMeResponse>({
    queryKey: ['auth', 'me'],
    queryFn: fetchAuthMe,
    retry: false,
    staleTime: 1000 * 60 * 60
  });
}
