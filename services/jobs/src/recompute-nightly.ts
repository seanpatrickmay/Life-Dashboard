// TODO: Trigger via Cloud Scheduler -> Pub/Sub when deployed to Cloud Run.
import { supabaseServiceRole } from '../../shared/supabase';
import { calculateReadinessScore } from '../../shared/calc';

interface DailyMetric {
  id: number;
  user_id: string;
  metric_date: string;
  sleep_minutes_total: number | null;
  sleep_efficiency: number | null;
  resting_hr: number | null;
  hrv_rmssd: number | null;
  training_load: number | null;
}

export async function recomputeNightly() {
  const supabase = supabaseServiceRole;
  const { data, error } = await supabase
    .from('daily_metrics')
    .select('*')
    .gte('metric_date', new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10));

  if (error) throw error;
  if (!data?.length) return;

  const grouped = data.reduce<Record<string, DailyMetric[]>>((acc, metric: any) => {
    if (!acc[metric.user_id]) acc[metric.user_id] = [];
    acc[metric.user_id].push(metric);
    return acc;
  }, {});

  for (const metrics of Object.values(grouped)) {
    metrics.sort((a, b) => a.metric_date.localeCompare(b.metric_date));

    for (let index = 0; index < metrics.length; index += 1) {
      const metric = metrics[index];
      const lookback = metrics.slice(Math.max(0, index - 14), index);
      const readiness = calculateReadinessScore({
        sleepMinutes: metric.sleep_minutes_total,
        sleepEfficiency: metric.sleep_efficiency,
        restingHr: metric.resting_hr,
        restingHrBaseline: average(lookback.map((item) => item.resting_hr)),
        hrvRmssd: metric.hrv_rmssd,
        hrvBaseline: average(lookback.map((item) => item.hrv_rmssd)),
        trainingLoad: metric.training_load,
        trainingLoadBaseline: average(lookback.map((item) => item.training_load))
      });

      const { error: updateError } = await supabase
        .from('daily_metrics')
        .update({ readiness_score: readiness, updated_at: new Date().toISOString() })
        .eq('id', metric.id);
      if (updateError) throw updateError;
    }
  }
}

function average(values: Array<number | null>): number | null {
  const filtered = values.filter((value): value is number => typeof value === 'number');
  if (!filtered.length) return null;
  const total = filtered.reduce((sum, value) => sum + value, 0);
  return total / filtered.length;
}
