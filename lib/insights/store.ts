import { getSupabaseServiceRoleClient } from '@/lib/supabase';
import type { InsightPayload } from '@/lib/llm/types';

export async function findExistingInsight(userId: string, topic: string, from: string, to: string) {
  const client = getSupabaseServiceRoleClient();
  const { data, error } = await client
    .from('insights')
    .select('*')
    .eq('user_id', userId)
    .eq('topic', topic)
    .eq('date_range', `[${from},${to}]`)
    .maybeSingle();
  if (error) throw error;
  return data;
}

export async function persistInsight(userId: string, payload: InsightPayload) {
  const client = getSupabaseServiceRoleClient();
  const { error } = await client.from('insights').insert({
    user_id: userId,
    topic: payload.topic,
    date_range: `[${payload.range.from},${payload.range.to}]`,
    summary: payload.summary,
    actions: payload.actions,
    model_metadata: {
      highlights: payload.highlights,
      bullets: payload.highlights,
      confidence: payload.confidence,
      references: payload.references,
      referencedMetrics:
        payload.referencedMetrics ?? Object.keys(payload.references ?? {}),
      ...(payload.metadata ?? {})
    },
    created_at: new Date().toISOString()
  });
  if (error) throw error;
}
