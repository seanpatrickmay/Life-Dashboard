import { useQuery } from '@tanstack/react-query';
import { fetchNutritionNutrients, type NutritionNutrient } from '../services/api';

const NUTRIENT_QUERY_KEY = ['nutrition', 'nutrients'];

export function useNutritionNutrients() {
  return useQuery<NutritionNutrient[]>({
    queryKey: NUTRIENT_QUERY_KEY,
    queryFn: fetchNutritionNutrients
  });
}

