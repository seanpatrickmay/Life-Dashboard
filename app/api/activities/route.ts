import { NextRequest, NextResponse } from 'next/server';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';
import { activityQuerySchema } from '@/lib/schemas/activities';

export async function GET(request: NextRequest) {
  try {
    const user = await requireAuthedUser();
    const search = activityQuerySchema.parse(Object.fromEntries(request.nextUrl.searchParams.entries()));
    const supabase = getSupabaseServerClient();

    let query = supabase
      .from('activities')
      .select('*', { count: 'exact' })
      .eq('user_id', user.id)
      .order('start_time', {
        ascending: false
      });

    if (search.from) {
      query = query.gte('start_time', new Date(search.from).toISOString());
    }

    if (search.to) {
      query = query.lte('start_time', new Date(search.to).toISOString());
    }

    const limit = search.limit ?? 50;
    const page = search.page ?? 1;
    const from = (page - 1) * limit;
    const to = from + limit - 1;

    query = query.range(from, to);

    const { data, error, count } = await query;
    if (error) throw error;

    return NextResponse.json({
      data,
      pagination: {
        limit,
        page,
        total: count
      }
    });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
