import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchUserProfile,
  updateUserProfile,
  type UserProfileData,
  type UserProfileResponse
} from '../services/api';

const PROFILE_QUERY_KEY = ['user', 'profile'];

export function useUserProfile() {
  const queryClient = useQueryClient();
  const profileQuery = useQuery<UserProfileResponse>({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: fetchUserProfile,
    staleTime: 1000 * 60 * 60
  });

  const updateMutation = useMutation({
    mutationFn: (payload: UserProfileData) => updateUserProfile(payload),
    onSuccess: (data) => {
      queryClient.setQueryData<UserProfileResponse>(PROFILE_QUERY_KEY, data);
    }
  });

  return {
    profileQuery,
    updateProfile: updateMutation.mutateAsync
  };
}
