import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createNutritionIngredient,
  fetchNutritionIngredients,
  updateNutritionIngredient,
  type NutritionIngredient
} from '../services/api';

const FOODS_QUERY_KEY = ['nutrition', 'foods'];

export function useNutritionFoods() {
  const queryClient = useQueryClient();
  const foodsQuery = useQuery({ queryKey: FOODS_QUERY_KEY, queryFn: fetchNutritionIngredients });

  const createMutation = useMutation({
    mutationFn: (payload: Partial<NutritionIngredient>) => createNutritionIngredient(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: FOODS_QUERY_KEY })
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<NutritionIngredient> }) =>
      updateNutritionIngredient(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: FOODS_QUERY_KEY })
  });

  return {
    foodsQuery,
    createFood: createMutation.mutateAsync,
    updateFood: updateMutation.mutateAsync
  };
}
