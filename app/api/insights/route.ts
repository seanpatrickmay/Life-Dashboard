import { NextRequest, NextResponse } from 'next/server';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';
import { insightsQuerySchema } from '@/lib/schemas/insights';

export async function GET(request: NextRequest) {
  try {
    const user = await requireAuthedUser();
    const search = insightsQuerySchema.parse(Object.fromEntries(request.nextUrl.searchParams.entries()));

    const supabase = getSupabaseServerClient();
    let query = supabase
      .from('insights')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false });

    if (search.topic) {
      query = query.eq('topic', search.topic);
    }

    if (search.from && search.to) {
      query = query.filter('date_range', 'overlaps', `[${search.from},${search.to}]`);
    }

    const { data, error } = await query;
    if (error) throw error;

    return NextResponse.json({ data });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
