// Thin proxy to the Cloud Run LLM service.
import { NextResponse } from 'next/server';

import { requireAuthedUser } from '@/lib/auth';
import { isSubscriptionActive } from '@/lib/billing';
import { rateLimit } from '@/lib/rate-limit';
import { getSupabaseServerClient } from '@/lib/supabase';
import { insightsRequestSchema } from '@/services/shared/schemas';

const LLM_ENDPOINT = process.env.LLM_SERVICE_URL;
const FREE_INSIGHTS_PER_MONTH = Number(process.env.NEXT_PUBLIC_FREE_INSIGHTS_LIMIT ?? 5);
const RATE_LIMIT_PER_MINUTE = Number(process.env.LLM_RATE_LIMIT_PER_MINUTE ?? 5);
const RATE_LIMIT_WINDOW_MS = Number(process.env.LLM_RATE_LIMIT_WINDOW_MS ?? 60_000);

export async function POST(request: Request) {
  if (!LLM_ENDPOINT) {
    return NextResponse.json({ error: 'LLM service URL not configured' }, { status: 503 });
  }

  const user = await requireAuthedUser();
  const json = await request.json();
  const parsed = insightsRequestSchema.safeParse({
    user_id: json.user_id ?? user.id,
    from: json.from ?? json.range?.from,
    to: json.to ?? json.range?.to,
    topics: json.topics ?? (json.topic ? [json.topic] : [])
  });

  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request', details: parsed.error.issues }, { status: 400 });
  }

  const payload = parsed.data;

  const rateLimiter = rateLimit(`insights:${payload.user_id}`, {
    max: RATE_LIMIT_PER_MINUTE,
    windowMs: RATE_LIMIT_WINDOW_MS
  });

  if (!rateLimiter.allowed) {
    const retrySeconds = Math.max(Math.ceil(rateLimiter.remaining / 1000), 1);
    return NextResponse.json(
      { error: `Too many insight requests. Try again in ${retrySeconds} second(s).` },
      {
        status: 429,
        headers: {
          'retry-after': retrySeconds.toString()
        }
      }
    );
  }

  const quotaResponse = await enforceInsightsQuota(payload.user_id, payload.topics.length);
  if (quotaResponse) {
    return quotaResponse;
  }

  const response = await fetch(`${LLM_ENDPOINT.replace(/\/$/, '')}/insights`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json'
    },
    body: JSON.stringify({
      user_id: payload.user_id,
      from: payload.from,
      to: payload.to,
      topics: payload.topics
    })
  });

  const text = await response.text();
  return new Response(text, {
    status: response.status,
    headers: {
      'content-type': response.headers.get('content-type') ?? 'application/json'
    }
  });
}

async function enforceInsightsQuota(userId: string, topicsRequested: number) {
  if (topicsRequested <= 0) {
    return NextResponse.json({ error: 'No topics requested' }, { status: 400 });
  }

  const supabase = getSupabaseServerClient();
  const { data: subscription, error: subscriptionError } = await supabase
    .from('subscriptions')
    .select('status,current_period_end')
    .eq('user_id', userId)
    .maybeSingle();

  if (subscriptionError) {
    throw subscriptionError;
  }

  const now = new Date();
  const isPremium = isSubscriptionActive(subscription, now);

  if (isPremium) {
    return null;
  }

  const startOfMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const { count, error: insightsError } = await supabase
    .from('insights')
    .select('id', { count: 'exact', head: true })
    .eq('user_id', userId)
    .gte('created_at', startOfMonth.toISOString());

  if (insightsError) {
    throw insightsError;
  }

  const existing = count ?? 0;
  if (existing + topicsRequested > FREE_INSIGHTS_PER_MONTH) {
    return NextResponse.json(
      {
        error: 'Insights quota reached. Upgrade to Pro for unlimited insights.'
      },
      { status: 402 }
    );
  }

  return null;
}
