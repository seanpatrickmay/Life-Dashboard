import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchNutritionSuggestions, quickLogFood } from '../services/api';

const SUGGESTIONS_KEY = ['nutrition', 'suggestions'];
const MENU_KEY = ['nutrition', 'menu'];
const SUMMARY_KEY = ['nutrition', 'daily'];
const HISTORY_KEY = ['nutrition', 'history'];

export function useNutritionSuggestions() {
  const queryClient = useQueryClient();

  const suggestionsQuery = useQuery({
    queryKey: SUGGESTIONS_KEY,
    queryFn: fetchNutritionSuggestions,
    staleTime: 1000 * 60 * 5,
  });

  const quickLogMutation = useMutation({
    mutationFn: quickLogFood,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SUGGESTIONS_KEY });
      void queryClient.invalidateQueries({ queryKey: MENU_KEY });
      void queryClient.invalidateQueries({ queryKey: SUMMARY_KEY });
      void queryClient.invalidateQueries({ queryKey: HISTORY_KEY });
    },
  });

  return {
    suggestionsQuery,
    quickLog: quickLogMutation.mutateAsync,
    isLogging: quickLogMutation.isPending,
  };
}
