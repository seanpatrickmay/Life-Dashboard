import crypto from 'node:crypto';

import {
  type BackfillOptions,
  type BackfillResult,
  type NormalizedDailyMetric,
  type ProviderStatus,
  type ProviderWebhookPayload
} from '@/lib/providers/types';
import { getSupabaseServiceRoleClient } from '@/lib/supabase';

const WITHINGS_BASE_URL = 'https://wbsapi.withings.net';

export interface WithingsTokenResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  scope: string;
  userId: string;
}

function getWithingsCredentials() {
  const clientId = process.env.WITHINGS_CLIENT_ID;
  const clientSecret = process.env.WITHINGS_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error('Withings credentials missing');
  }
  return { clientId, clientSecret };
}

export function withingsAuthUrl(redirectUri: string, state: string) {
  const { clientId } = getWithingsCredentials();
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    state,
    scope: 'user.metrics',
    redirect_uri: redirectUri
  });

  return `https://account.withings.com/oauth2_user/authorize2?${params.toString()}`;
}

export async function exchangeWithingsCode(code: string, redirectUri: string): Promise<WithingsTokenResponse> {
  const { clientId, clientSecret } = getWithingsCredentials();

  const response = await fetch(`${WITHINGS_BASE_URL}/v2/oauth2`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      action: 'requesttoken',
      grant_type: 'authorization_code',
      client_id: clientId,
      client_secret: clientSecret,
      code,
      redirect_uri: redirectUri
    }).toString()
  });

  const json = await response.json();
  if (json.status !== 0) {
    throw new Error(`Withings token exchange failed: ${json.error ?? json.status}`);
  }

  return normalizeTokenResponse(json.body);
}

export async function refreshWithingsToken(refreshToken: string): Promise<WithingsTokenResponse> {
  const { clientId, clientSecret } = getWithingsCredentials();

  const response = await fetch(`${WITHINGS_BASE_URL}/v2/oauth2`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      action: 'requesttoken',
      grant_type: 'refresh_token',
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken
    }).toString()
  });

  const json = await response.json();
  if (json.status !== 0) {
    throw new Error(`Withings token refresh failed: ${json.error ?? json.status}`);
  }

  return normalizeTokenResponse(json.body);
}

function normalizeTokenResponse(body: any): WithingsTokenResponse {
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    expiresIn: body.expires_in,
    scope: body.scope,
    userId: body.userid?.toString() ?? ''
  };
}

export function verifyWithingsWebhook(request: Request, rawBody: string): boolean {
  const signature = request.headers.get('signature');
  const secret = process.env.WITHINGS_WEBHOOK_SECRET;
  if (!signature || !secret) return false;

  const mac = crypto.createHmac('sha256', secret).update(rawBody).digest('base64');
  return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(mac));
}

export async function parseWithingsWebhook(request: Request): Promise<ProviderWebhookPayload> {
  const raw = await request.text();
  if (!verifyWithingsWebhook(request, raw)) {
    throw new Error('Invalid Withings signature');
  }

  const body = JSON.parse(raw);
  return {
    provider: 'withings',
    event: body?.notification?.category ?? 'unknown',
    receivedAt: new Date().toISOString(),
    data: body
  };
}

export function normalizeWithingsWeight(payload: any): NormalizedDailyMetric {
  return {
    date: new Date(payload.date * 1000).toISOString().slice(0, 10),
    weightKg: payload?.weight,
    bodyFatPct: payload?.fat_ratio
  };
}

export async function backfillWithingsData(options: BackfillOptions): Promise<BackfillResult> {
  const supabase = getSupabaseServiceRoleClient();
  const days = Math.min(Math.max(options.days, 1), 365);
  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);

  const measurements = await fetchMeasurements(options.accessToken, start, end);

  let metricsUpserted = 0;
  for (const measurement of measurements) {
    const normalized = normalizeWithingsWeight(measurement);
    const { error } = await supabase.from('daily_metrics').upsert(
      {
        user_id: options.userId,
        metric_date: normalized.date,
        weight_kg: normalized.weightKg,
        body_fat_pct: normalized.bodyFatPct,
        updated_at: new Date().toISOString()
      },
      { onConflict: 'user_id,metric_date' }
    );

    if (error) {
      console.error('[withings] failed to upsert measurement', error);
      throw error;
    }
    metricsUpserted += 1;
  }

  if (measurements.length) {
    await supabase.from('raw_events').insert(
      measurements.map((measurement) => ({
        user_id: options.userId,
        provider: 'withings',
        payload: measurement,
        received_at: new Date().toISOString()
      }))
    );
  }

  return {
    importedDays: measurements.length,
    rawEventsStored: measurements.length,
    metricsUpserted,
    activitiesUpserted: 0
  };
}

async function fetchMeasurements(accessToken: string, start: Date, end: Date) {
  const response = await fetch(`${WITHINGS_BASE_URL}/measure`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      action: 'getmeas',
      access_token: accessToken,
      startdate: Math.floor(start.getTime() / 1000).toString(),
      enddate: Math.floor(end.getTime() / 1000).toString()
    }).toString()
  });

  const json = await response.json();
  if (json.status !== 0) {
    console.warn('[withings] measurements fetch failed', json.status);
    return [];
  }

  const groups = json.body?.measuregrps ?? [];
  return groups;
}

export function resolveWithingsStatus(latestSyncAt?: string | null, status?: string | null): ProviderStatus {
  if (status === 'paused' || status === 'revoked') return status;
  if (!latestSyncAt) return 'disconnected';
  const lastSync = new Date(latestSyncAt);
  const hours = (Date.now() - lastSync.getTime()) / 36e5;
  if (hours > 168) return 'error';
  return 'connected';
}

export async function handleWithingsReconnect(options: BackfillOptions) {
  const result = await backfillWithingsData(options);
  console.info('[withings] reconnection backfill complete', { userId: options.userId, result });
  await getSupabaseServiceRoleClient()
    .from('connections')
    .update({ status: 'connected', latest_sync_at: new Date().toISOString() })
    .eq('user_id', options.userId)
    .eq('provider', 'withings');
}
