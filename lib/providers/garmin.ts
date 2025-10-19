import crypto from 'node:crypto';

import type {
  BackfillOptions,
  BackfillResult,
  NormalizedActivity,
  NormalizedDailyMetric,
  ProviderStatus,
  ProviderWebhookPayload
} from '@/lib/providers/types';
import { getSupabaseServiceRoleClient } from '@/lib/supabase';

const GARMIN_BASE_URL = 'https://connectapi.garmin.com';
const GARMIN_API_BASE = 'https://apis.garmin.com';

export interface GarminTokenResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  scope: string;
}

export interface GarminWebhookEnvelope {
  eventType: string;
  data: unknown;
  createdTime: string;
}

function getClientCredentials() {
  const clientId = process.env.GARMIN_CLIENT_ID;
  const clientSecret = process.env.GARMIN_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error('Garmin credentials missing');
  }
  return { clientId, clientSecret };
}

export function garminAuthUrl(redirectUri: string, state: string) {
  const { clientId } = getClientCredentials();
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: 'code',
    redirect_uri: redirectUri,
    scope: 'activity sleep heart-rate stress body-composition'
  });

  if (state) params.set('state', state);

  return `${GARMIN_BASE_URL}/oauth-service/oauth/authorize?${params.toString()}`;
}

export async function exchangeGarminCode(code: string, redirectUri: string): Promise<GarminTokenResponse> {
  const { clientId, clientSecret } = getClientCredentials();

  const response = await fetch(`${GARMIN_BASE_URL}/oauth-service/oauth/token`, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString('base64')}`,
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: redirectUri
    }).toString()
  });

  if (!response.ok) {
    throw new Error(`Garmin token exchange failed: ${await response.text()}`);
  }

  const json = await response.json();
  return normalizeTokenResponse(json);
}

export async function refreshGarminToken(refreshToken: string): Promise<GarminTokenResponse> {
  const { clientId, clientSecret } = getClientCredentials();

  const response = await fetch(`${GARMIN_BASE_URL}/oauth-service/oauth/token`, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString('base64')}`,
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: refreshToken
    }).toString()
  });

  if (!response.ok) {
    throw new Error(`Garmin token refresh failed: ${await response.text()}`);
  }

  const json = await response.json();
  return normalizeTokenResponse(json);
}

function normalizeTokenResponse(json: any): GarminTokenResponse {
  return {
    accessToken: json.access_token,
    refreshToken: json.refresh_token ?? json.refresh_token_expires_in,
    expiresIn: Number(json.expires_in ?? 0),
    scope: json.scope ?? ''
  };
}

export function verifyGarminWebhook(signature: string | null, rawBody: string): boolean {
  const secret = process.env.GARMIN_WEBHOOK_SECRET;
  if (!secret || !signature) return false;

  const computed = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
  return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(computed));
}

export function normalizeGarminDaily(payload: any): NormalizedDailyMetric {
  return {
    date: payload.calendarDate,
    energyBurnedKcal: payload?.caloriesBurned,
    steps: payload?.steps,
    sleepMinutesTotal: payload?.sleepingSeconds ? Math.round(payload.sleepingSeconds / 60) : undefined,
    sleepEfficiency: payload?.sleepEfficiency,
    restingHr: payload?.restingHeartRate,
    hrvRmssd: payload?.hrvRmssd,
    stressScore: payload?.stressLevel,
    trainingLoad: payload?.trainingLoad,
    weightKg: payload?.weight,
    bodyFatPct: payload?.bodyFat
  };
}

export function normalizeGarminActivity(payload: any): NormalizedActivity {
  return {
    sourceId: payload?.activityId?.toString(),
    name: payload?.activityName,
    sportType: payload?.activityType,
    startTime: payload?.startTimeLocal ?? payload?.startTimeGMT,
    durationSeconds: payload?.duration,
    distanceMeters: payload?.distance,
    avgHr: payload?.averageHR,
    maxHr: payload?.maxHR,
    trimp: payload?.trimp,
    tssEst: payload?.trainingStressScore,
    calories: payload?.calories,
    raw: payload
  };
}

export async function fetchGarminWebhookPayload(request: Request): Promise<ProviderWebhookPayload> {
  const raw = await request.text();
  const signature = request.headers.get('x-garmin-signature-sha256');
  if (!verifyGarminWebhook(signature, raw)) {
    throw new Error('Invalid Garmin signature');
  }

  const body = JSON.parse(raw);
  const event = body[0] as GarminWebhookEnvelope;

  return {
    provider: 'garmin',
    event: event.eventType,
    receivedAt: event.createdTime,
    data: event.data
  };
}

export async function backfillGarminData(options: BackfillOptions): Promise<BackfillResult> {
  const supabase = getSupabaseServiceRoleClient();
  const days = Math.min(Math.max(options.days, 1), 365);
  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);

  const dailySummaries = await fetchGarminDailySummaries(options.accessToken, start, end);
  const activities = await fetchGarminActivities(options.accessToken, start, end);

  let metricsUpserted = 0;
  let activitiesUpserted = 0;

  for (const summary of dailySummaries) {
    const normalized = normalizeGarminDaily(summary);
    const { error } = await supabase.from('daily_metrics').upsert(
      {
        user_id: options.userId,
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
      },
      { onConflict: 'user_id,metric_date' }
    );

    if (error) {
      console.error('[garmin] failed to upsert daily metric', error);
      throw error;
    }
    metricsUpserted += 1;
  }

  for (const activity of activities) {
    const normalizedActivity = normalizeGarminActivity(activity);
    const { error } = await supabase.from('activities').upsert(
      {
        user_id: options.userId,
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
      { onConflict: 'user_id,source,source_id' }
    );

    if (error) {
      console.error('[garmin] failed to upsert activity', error);
      throw error;
    }
    activitiesUpserted += 1;
  }

  await supabase.from('raw_events').insert(
    dailySummaries.map((summary) => ({
      user_id: options.userId,
      provider: 'garmin',
      payload: summary,
      received_at: new Date().toISOString()
    }))
  );

  return {
    importedDays: dailySummaries.length,
    rawEventsStored: dailySummaries.length,
    metricsUpserted,
    activitiesUpserted
  };
}

async function fetchGarminDailySummaries(accessToken: string, start: Date, end: Date) {
  const url = `${GARMIN_API_BASE}/wellness-service/wellness/dailySummary/${formatDate(start)}/${formatDate(end)}`;
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });

  if (!response.ok) {
    console.warn('[garmin] daily summary fetch failed', response.status);
    return [];
  }

  const json = await response.json();
  return Array.isArray(json) ? json : [];
}

async function fetchGarminActivities(accessToken: string, start: Date, end: Date) {
  const url = `${GARMIN_API_BASE}/activity-service/activity/activities?startDate=${formatDate(start)}&endDate=${formatDate(end)}`;
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });

  if (!response.ok) {
    console.warn('[garmin] activities fetch failed', response.status);
    return [];
  }

  const json = await response.json();
  return Array.isArray(json) ? json : [];
}

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

export function resolveConnectionStatus(latestSyncAt?: string | null, status?: string | null): ProviderStatus {
  if (status === 'paused' || status === 'revoked') return status;
  if (!latestSyncAt) return 'disconnected';
  const lastSync = new Date(latestSyncAt);
  const hours = (Date.now() - lastSync.getTime()) / 36e5;
  if (hours > 72) return 'error';
  return 'connected';
}

export async function handleReconnect(options: BackfillOptions & { lastSync?: string | null }) {
  const result = await backfillGarminData(options);
  console.info('[garmin] reconnection backfill complete', { userId: options.userId, result });
  await getSupabaseServiceRoleClient()
    .from('connections')
    .update({ status: 'connected', latest_sync_at: new Date().toISOString() })
    .eq('user_id', options.userId)
    .eq('provider', 'garmin');
}
