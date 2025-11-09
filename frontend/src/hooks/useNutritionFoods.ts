import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createNutritionFood,
  fetchNutritionFoods,
  updateNutritionFood,
  type NutritionFood
} from '../services/api';

const FOODS_QUERY_KEY = ['nutrition', 'foods'];

export function useNutritionFoods() {
  const queryClient = useQueryClient();
  const foodsQuery = useQuery({ queryKey: FOODS_QUERY_KEY, queryFn: fetchNutritionFoods });

  const createMutation = useMutation({
    mutationFn: (payload: Partial<NutritionFood>) => createNutritionFood(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: FOODS_QUERY_KEY })
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<NutritionFood> }) =>
      updateNutritionFood(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: FOODS_QUERY_KEY })
  });

  return {
    foodsQuery,
    createFood: createMutation.mutateAsync,
    updateFood: updateMutation.mutateAsync
  };
}
