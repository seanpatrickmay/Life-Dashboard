import { supabaseServiceRole } from './supabase';

const CACHE_KEY_FIELD = 'cache_key';

export function buildInsightCacheKey(userId: string, from: string, to: string, topics: string[]) {
  return [userId, from, to, [...topics].sort().join('|')].join(':');
}

interface CachedInsightRow {
  topic: string;
  summary: string;
  actions: unknown;
  model_metadata: Record<string, unknown> | null;
  created_at: string;
}

export async function getCachedInsights(
  userId: string,
  from: string,
  to: string,
  cacheKey: string,
  topics: string[]
) {
  if (!topics.length) return null;

  const { data, error } = await supabaseServiceRole
    .from('insights')
    .select('topic,summary,actions,model_metadata,created_at')
    .eq('user_id', userId)
    .eq('date_range', `[${from},${to}]`)
    .eq(`model_metadata->>${CACHE_KEY_FIELD}`, cacheKey)
    .in('topic', topics);

  if (error) throw error;
  if (!data?.length) return null;

  const entries = new Map<string, CachedInsightRow>();
  for (const row of data as CachedInsightRow[]) {
    entries.set(row.topic, row);
  }
  if (entries.size !== topics.length) {
    return null;
  }

  return { cacheKey, entries };
}

export interface UpsertInsightPayload {
  userId: string;
  topic: string;
  from: string;
  to: string;
  summary: string;
  actions: string[];
  highlights: string[];
  confidence: number;
  references: Record<string, unknown>;
  cacheKey: string;
}

export async function upsertInsight(payload: UpsertInsightPayload) {
  const referencedMetrics = Object.keys(payload.references ?? {});
  const metadata = {
    cache_key: payload.cacheKey,
    highlights: payload.highlights,
    bullets: payload.highlights,
    confidence: payload.confidence,
    references: payload.references,
    referencedMetrics
  };

  const { error } = await supabaseServiceRole.from('insights').upsert(
    {
      user_id: payload.userId,
      topic: payload.topic,
      date_range: `[${payload.from},${payload.to}]`,
      summary: payload.summary,
      actions: payload.actions,
      model_metadata: metadata,
      created_at: new Date().toISOString()
    },
    {
      onConflict: 'user_id,topic,date_range'
    }
  );

  if (error) throw error;
}
