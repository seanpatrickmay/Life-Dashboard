import { NextResponse } from 'next/server';
import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';

const providerSchema = z.object({
  provider: z.enum(['garmin', 'withings', 'manual'])
});

const connectionActionSchema = z.object({
  provider: providerSchema.shape.provider,
  action: z.enum(['resync']).default('resync'),
  days: z.coerce.number().int().min(1).max(365).default(30)
});

export async function DELETE(request: Request) {
  try {
    const user = await requireAuthedUser();
    const { provider } = providerSchema.parse(await request.json());

    const supabase = getSupabaseServerClient();
    const { error } = await supabase
      .from('connections')
      .update({ status: 'revoked', access_token_encrypted: null, refresh_token_encrypted: null, updated_at: new Date().toISOString() })
      .eq('user_id', user.id)
      .eq('provider', provider);

    if (error) throw error;

    revalidatePath('/settings');

    return NextResponse.json({ status: 'revoked' });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}

export async function POST(request: Request) {
  try {
    const user = await requireAuthedUser();
    const { provider, action, days } = connectionActionSchema.parse(await request.json());

    const jobsUrl = process.env.JOBS_SERVICE_URL;
    if (!jobsUrl) {
      return NextResponse.json(
        { error: 'Jobs service URL not configured' },
        { status: 503 }
      );
    }

    const url = new URL(`${jobsUrl.replace(/\/$/, '')}/backfill`);
    url.searchParams.set('provider', provider);
    url.searchParams.set('days', String(days));
    url.searchParams.set('userId', user.id);

    const response = await fetch(url.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ userId: user.id })
    });

    if (!response.ok) {
      const text = await response.text();
      return NextResponse.json({ error: text || 'Failed to queue backfill' }, { status: response.status });
    }

    revalidatePath('/settings');

    return NextResponse.json({ status: 'queued' });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
