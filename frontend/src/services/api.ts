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

export const fetchInsight = async (): Promise<InsightResponse> => {
  const { data } = await api.get('/api/insights/daily');
  return data;
};

export const fetchMetricsOverview = async (rangeDays = 7): Promise<MetricsOverview> => {
  const { data } = await api.get('/api/metrics/overview', { params: { range_days: rangeDays } });
  return data;
};
