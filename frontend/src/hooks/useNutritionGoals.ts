import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchNutritionGoals, updateNutritionGoal, type NutritionGoal } from '../services/api';

const GOALS_QUERY_KEY = ['nutrition', 'goals'];
const SUMMARY_QUERY_KEY = ['nutrition', 'summary'];
const HISTORY_QUERY_KEY = ['nutrition', 'history'];

export function useNutritionGoals() {
  const queryClient = useQueryClient();
  const goalsQuery = useQuery({ queryKey: GOALS_QUERY_KEY, queryFn: fetchNutritionGoals });

  const updateMutation = useMutation({
    mutationFn: ({ slug, goal }: { slug: string; goal: number }) => updateNutritionGoal(slug, goal),
    onSuccess: (updatedGoal) => {
      queryClient.setQueryData<NutritionGoal[]>(GOALS_QUERY_KEY, (prev) => {
        if (!prev) return prev;
        return prev.map((goalItem) => (goalItem.slug === updatedGoal.slug ? updatedGoal : goalItem));
      });
      void queryClient.invalidateQueries({ queryKey: SUMMARY_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: HISTORY_QUERY_KEY });
    }
  });

  return {
    goalsQuery,
    updateGoal: updateMutation.mutateAsync
  };
}
