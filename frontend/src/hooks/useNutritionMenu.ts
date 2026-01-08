import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteNutritionIntake,
  fetchNutritionMenu,
  updateNutritionIntake,
  type NutritionMenuResponse
} from '../services/api';

const MENU_QUERY_KEY = ['nutrition', 'menu'];
const SUMMARY_QUERY_KEY = ['nutrition', 'summary'];
const HISTORY_QUERY_KEY = ['nutrition', 'history'];

export function useNutritionMenu() {
  const queryClient = useQueryClient();

  const menuQuery = useQuery<NutritionMenuResponse>({
    queryKey: MENU_QUERY_KEY,
    queryFn: fetchNutritionMenu
  });

  const invalidateIntakeQueries = () => {
    void queryClient.invalidateQueries({ queryKey: MENU_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: SUMMARY_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: HISTORY_QUERY_KEY });
  };

  const updateMutation = useMutation({
    mutationFn: (payload: { id: number; quantity: number; unit: string }) =>
      updateNutritionIntake(payload.id, { quantity: payload.quantity, unit: payload.unit }),
    onSuccess: invalidateIntakeQueries
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNutritionIntake(id),
    onSuccess: invalidateIntakeQueries
  });

  return {
    menuQuery,
    updateEntry: updateMutation.mutateAsync,
    deleteEntry: deleteMutation.mutateAsync
  };
}
