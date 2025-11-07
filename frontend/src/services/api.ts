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
