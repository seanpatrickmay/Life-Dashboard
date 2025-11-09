import { useQuery } from '@tanstack/react-query';
import { fetchNutritionDailySummary, fetchNutritionHistory } from '../services/api';

const DAILY_KEY = ['nutrition', 'summary'];
const HISTORY_KEY = ['nutrition', 'history'];

export function useNutritionDailySummary(day?: string) {
  return useQuery({ queryKey: [...DAILY_KEY, day], queryFn: () => fetchNutritionDailySummary(day) });
}

export function useNutritionHistory(days = 14) {
  return useQuery({ queryKey: [...HISTORY_KEY, days], queryFn: () => fetchNutritionHistory(days) });
}
