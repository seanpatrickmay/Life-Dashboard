// Normalization helpers used by both webhook ingestion and backfill jobs.
import { supabaseServiceRole } from '../../shared/supabase';
import type { ProviderWebhookPayload } from '@/lib/providers/types';
import { normalizeGarminActivity, normalizeGarminDaily } from '@/lib/providers/garmin';
import { normalizeWithingsWeight } from '@/lib/providers/withings';

export async function processProviderPayload(userId: string, payload: ProviderWebhookPayload) {
  const supabase = supabaseServiceRole;

  switch (payload.provider) {
    case 'garmin':
      await handleGarminPayload(userId, payload, supabase);
      break;
    case 'withings':
      await handleWithingsPayload(userId, payload, supabase);
      break;
    default:
      break;
  }
}

async function handleGarminPayload(userId: string, payload: ProviderWebhookPayload, supabase: typeof supabaseServiceRole) {
  const data = payload.data as any;

  if (payload.event.includes('daily_summary')) {
    const normalized = normalizeGarminDaily(data);
    const { error } = await supabase.from('daily_metrics').upsert({
      user_id: userId,
      metric_date: normalized.date,
      energy_burned_kcal: normalized.energyBurnedKcal,
      steps: normalized.steps,
      sleep_minutes_total: normalized.sleepMinutesTotal,
      sleep_efficiency: normalized.sleepEfficiency,
      resting_hr: normalized.restingHr,
      hrv_rmssd: normalized.hrvRmssd,
      stress_score: normalized.stressScore,
      training_load: normalized.trainingLoad,
      weight_kg: normalized.weightKg,
      body_fat_pct: normalized.bodyFatPct,
      updated_at: new Date().toISOString()
    });
    if (error) throw error;
  }

  if (payload.event.includes('activity')) {
    const normalizedActivity = normalizeGarminActivity(data);
    const { error } = await supabase.from('activities').upsert(
      {
        user_id: userId,
        source: 'garmin',
        source_id: normalizedActivity.sourceId,
        name: normalizedActivity.name,
        sport_type: normalizedActivity.sportType,
        start_time: normalizedActivity.startTime,
        duration_s: normalizedActivity.durationSeconds,
        distance_m: normalizedActivity.distanceMeters,
        avg_hr: normalizedActivity.avgHr,
        max_hr: normalizedActivity.maxHr,
        trimp: normalizedActivity.trimp,
        tss_est: normalizedActivity.tssEst,
        calories: normalizedActivity.calories,
        data: normalizedActivity.raw,
        updated_at: new Date().toISOString()
      },
      {
        onConflict: 'user_id,source,source_id'
      }
    );
    if (error) throw error;
  }
}

async function handleWithingsPayload(userId: string, payload: ProviderWebhookPayload, supabase: typeof supabaseServiceRole) {
  const measurements = payload.data?.body ?? payload.data?.body?.measuregrps ?? [];
  for (const measurement of measurements) {
    const normalized = normalizeWithingsWeight(measurement);
    const { error } = await supabase.from('daily_metrics').upsert({
      user_id: userId,
      metric_date: normalized.date,
      weight_kg: normalized.weightKg,
      body_fat_pct: normalized.bodyFatPct,
      updated_at: new Date().toISOString()
    });
    if (error) throw error;
  }
}
