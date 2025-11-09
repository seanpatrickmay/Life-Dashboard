import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteNutritionIntake,
  fetchNutritionMenu,
  updateNutritionIntake,
  type NutritionMenuResponse
} from '../services/api';

const MENU_QUERY_KEY = ['nutrition', 'menu'];

export function useNutritionMenu() {
  const queryClient = useQueryClient();

  const menuQuery = useQuery<NutritionMenuResponse>({
    queryKey: MENU_QUERY_KEY,
    queryFn: fetchNutritionMenu
  });

  const updateMutation = useMutation({
    mutationFn: (payload: { id: number; quantity: number; unit: string }) =>
      updateNutritionIntake(payload.id, { quantity: payload.quantity, unit: payload.unit }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MENU_QUERY_KEY })
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNutritionIntake(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MENU_QUERY_KEY })
  });

  return {
    menuQuery,
    updateEntry: updateMutation.mutateAsync,
    deleteEntry: deleteMutation.mutateAsync
  };
}

