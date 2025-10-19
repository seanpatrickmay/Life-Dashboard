import { getSupabaseServiceRoleClient } from '@/lib/supabase';
import type { BackfillOptions, BackfillResult, ProviderWebhookPayload } from '@/lib/providers/types';
import { backfillGarminData, fetchGarminWebhookPayload } from '@/lib/providers/garmin';
import { backfillWithingsData, parseWithingsWebhook } from '@/lib/providers/withings';

type ProviderHandler = {
  parseWebhook(request: Request): Promise<ProviderWebhookPayload>;
  backfill(options: BackfillOptions): Promise<BackfillResult>;
};

const providers: Record<string, ProviderHandler> = {
  garmin: {
    parseWebhook: fetchGarminWebhookPayload,
    backfill: backfillGarminData
  },
  withings: {
    parseWebhook: parseWithingsWebhook,
    backfill: backfillWithingsData
  }
};

export async function upsertRawEvent(payload: ProviderWebhookPayload, userId: string) {
  const client = getSupabaseServiceRoleClient();
  await client.from('raw_events').insert({
    user_id: userId,
    provider: payload.provider,
    event_type: payload.event,
    payload: payload.data,
    received_at: payload.receivedAt
  });
}

export function getProviderHandler(provider: string): ProviderHandler {
  const handler = providers[provider];
  if (!handler) {
    throw new Error(`Unsupported provider: ${provider}`);
  }
  return handler;
}
