import { NextRequest, NextResponse } from 'next/server';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';
import { dateParamSchema } from '@/lib/schemas/dates';

export async function GET(_request: NextRequest, context: { params: { date: string } }) {
  try {
    const user = await requireAuthedUser();
    const { date } = dateParamSchema.parse({ date: context.params.date });

    const supabase = getSupabaseServerClient();

    const [{ data: metrics, error: metricsError }, { data: readiness }, { data: macro }, { data: micro }, { data: activities }] =
      await Promise.all([
        supabase
          .from('daily_metrics')
          .select('*')
          .eq('user_id', user.id)
          .eq('metric_date', date)
          .maybeSingle(),
        supabase
          .from('v_daily_readiness')
          .select('*')
          .eq('user_id', user.id)
          .eq('metric_date', date)
          .maybeSingle(),
        supabase
          .from('v_macro_compliance')
          .select('*')
          .eq('user_id', user.id)
          .eq('entry_date', date)
          .maybeSingle(),
        supabase
          .from('v_micronutrient_coverage')
          .select('*')
          .eq('user_id', user.id)
          .eq('entry_date', date)
          .maybeSingle(),
        supabase
          .from('activities')
          .select('id, name, sport_type, start_time, duration_s, distance_m, tss_est, trimp')
          .eq('user_id', user.id)
          .gte('start_time', new Date(date).toISOString())
          .lt('start_time', new Date(new Date(date).getTime() + 86400000).toISOString())
          .order('start_time', { ascending: true })
      ]);

    if (metricsError && metricsError.code !== 'PGRST116') {
      throw metricsError;
    }

    return NextResponse.json({
      date,
      metrics,
      readiness,
      macro,
      micro,
      activities
    });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 500 });
  }
}
