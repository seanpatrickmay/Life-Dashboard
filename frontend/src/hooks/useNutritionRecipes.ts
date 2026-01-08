import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchNutritionRecipes,
  fetchNutritionRecipe,
  createNutritionRecipe,
  updateNutritionRecipe,
  type NutritionRecipe
} from '../services/api';

const RECIPES_LIST_KEY = ['nutrition', 'recipes'];

export function useNutritionRecipes(recipeId?: number) {
  const queryClient = useQueryClient();

  const recipesQuery = useQuery({ queryKey: RECIPES_LIST_KEY, queryFn: fetchNutritionRecipes });

  const recipeQuery = useQuery({
    queryKey: [...RECIPES_LIST_KEY, recipeId],
    queryFn: () => fetchNutritionRecipe(recipeId as number),
    enabled: typeof recipeId === 'number'
  });

  const createMutation = useMutation({
    mutationFn: (payload: Partial<NutritionRecipe>) => createNutritionRecipe(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RECIPES_LIST_KEY })
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<NutritionRecipe> }) =>
      updateNutritionRecipe(id, payload),
    onSuccess: (data) => {
      queryClient.setQueryData<NutritionRecipe>([...RECIPES_LIST_KEY, data.id], data);
      queryClient.invalidateQueries({ queryKey: RECIPES_LIST_KEY });
    }
  });

  return {
    recipesQuery,
    recipeQuery,
    createRecipe: createMutation.mutateAsync,
    updateRecipe: updateMutation.mutateAsync
  };
}
