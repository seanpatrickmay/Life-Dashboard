import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const api = axios.create({
  baseURL,
  timeout: 10000
});

export type InsightResponse = {
  metric_date: string;
  readiness_score: number | null;
  readiness_label: string | null;
  narrative: string;
  source_model: string;
  last_updated: string;
  refreshing?: boolean;
  greeting?: string | null;
  hrv_value_ms?: number | null;
  hrv_note?: string | null;
  hrv_score?: number | null;
  rhr_value_bpm?: number | null;
  rhr_note?: string | null;
  rhr_score?: number | null;
  sleep_value_hours?: number | null;
  sleep_note?: string | null;
  sleep_score?: number | null;
  training_load_value?: number | null;
  training_load_note?: string | null;
  training_load_score?: number | null;
  morning_note?: string | null;
};

export type MetricDelta = {
  value: number | null;
  value_unit: string;
  reference_value: number | null;
  reference_label: string;
  delta: number | null;
  delta_unit: string;
};

export type ReadinessMetricsSummary = {
  date: string;
  hrv: MetricDelta;
  rhr: MetricDelta;
  sleep: MetricDelta;
  training_load: MetricDelta;
};

export type MetricsOverview = {
  generated_at: string;
  range_label: string;
  training_volume_hours: number;
  training_volume_window_days: number;
  training_load_avg: number | null;
  training_load_trend: { timestamp: string; value: number | null }[];
  hrv_trend_ms: { timestamp: string; value: number | null }[];
  rhr_trend_bpm: { timestamp: string; value: number | null }[];
  sleep_trend_hours: { timestamp: string; value: number | null }[];
};

export type SceneTimeResponse = {
  iso: string;
  time_zone: string;
  hour_decimal: number;
  moment: 'morning' | 'noon' | 'twilight' | 'night';
};

export const fetchInsight = async (): Promise<InsightResponse> => {
  const { data } = await api.get('/api/insights/daily');
  return data;
};

export const fetchMetricsOverview = async (rangeDays = 7): Promise<MetricsOverview> => {
  const { data } = await api.get('/api/metrics/overview', { params: { range_days: rangeDays } });
  return data;
};

export const fetchReadinessSummary = async (): Promise<ReadinessMetricsSummary> => {
  const { data } = await api.get('/api/metrics/readiness-summary');
  return data;
};

export const fetchSceneTime = async (): Promise<SceneTimeResponse> => {
  const { data } = await api.get('/api/time');
  return data;
};

// Nutrition

export type NutritionNutrient = {
  slug: string;
  display_name: string;
  category: string;
  group: string;
  unit: string;
  default_goal: number;
};

export type NutritionFood = {
  id: number;
  name: string;
  default_unit: string;
  status: string;
  source?: string | null;
  nutrients: Record<string, number | null>;
};

export type NutritionGoal = {
  slug: string;
  display_name: string;
  unit: string;
  category: string;
  group: string;
  goal: number;
  default_goal: number;
};

export type NutritionSummary = {
  date: string;
  nutrients: Array<{
    slug: string;
    display_name: string;
    group: string;
    unit: string;
    amount: number | null;
    goal: number | null;
    percent_of_goal: number | null;
  }>;
};

export type NutritionHistory = {
  window_days: number;
  nutrients: Array<{
    slug: string;
    display_name: string;
    group: string;
    unit: string;
    average_amount: number | null;
    goal: number | null;
    percent_of_goal: number | null;
  }>;
};

export type ClaudeChatResponse = {
  session_id: string;
  reply: string;
  logged_entries: Array<{
    food_id: number;
    food_name: string;
    quantity: number;
    unit: string;
    status: string;
    created?: boolean;
  }>;
};

export const fetchNutritionNutrients = async (): Promise<NutritionNutrient[]> => {
  const { data } = await api.get('/api/nutrition/nutrients');
  return data;
};

export type NutritionMenuResponse = {
  day: string;
  entries: Array<{
    id: number;
    food_id: number;
    food_name?: string | null;
    quantity: number;
    unit: string;
    source: string;
  }>;
};

export const fetchNutritionMenu = async (day?: string): Promise<NutritionMenuResponse> => {
  const { data } = await api.get('/api/nutrition/intake/menu', { params: { day } });
  return data;
};

export const updateNutritionIntake = async (
  intakeId: number,
  payload: { quantity: number; unit: string }
) => {
  const { data } = await api.patch(`/api/nutrition/intake/${intakeId}`, payload);
  return data;
};

export const deleteNutritionIntake = async (intakeId: number) => {
  await api.delete(`/api/nutrition/intake/${intakeId}`);
};

export const fetchNutritionFoods = async (): Promise<NutritionFood[]> => {
  const { data } = await api.get('/api/nutrition/foods');
  return data;
};

export const createNutritionFood = async (payload: Partial<NutritionFood>) => {
  const { data } = await api.post('/api/nutrition/foods', payload);
  return data as NutritionFood;
};

export const updateNutritionFood = async (id: number, payload: Partial<NutritionFood>) => {
  const { data } = await api.patch(`/api/nutrition/foods/${id}`, payload);
  return data as NutritionFood;
};

export const fetchNutritionGoals = async (): Promise<NutritionGoal[]> => {
  const { data } = await api.get('/api/nutrition/goals');
  return data;
};

export const updateNutritionGoal = async (slug: string, goal: number) => {
  const { data } = await api.put(`/api/nutrition/goals/${slug}`, { goal });
  return data as NutritionGoal;
};

export const logManualIntake = async (payload: { food_id: number; quantity: number; unit: string; day?: string }) => {
  const { data } = await api.post('/api/nutrition/intake/manual', payload);
  return data as { id: number } & typeof payload;
};

export const fetchNutritionDailySummary = async (day?: string): Promise<NutritionSummary> => {
  const { data } = await api.get('/api/nutrition/intake/daily', { params: { day } });
  return data;
};

export const fetchNutritionHistory = async (days = 14): Promise<NutritionHistory> => {
  const { data } = await api.get('/api/nutrition/intake/history', { params: { days } });
  return data;
};

export const sendClaudeMessage = async (message: string, session_id?: string): Promise<ClaudeChatResponse> => {
  const { data } = await api.post('/api/nutrition/claude/message', { message, session_id });
  return data;
};
