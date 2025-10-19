import { NextResponse } from 'next/server';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';
import { nutritionGoalsSchema } from '@/lib/schemas/goals';

export async function POST(request: Request) {
  try {
    const user = await requireAuthedUser();
    const body = await request.json();
    const payload = nutritionGoalsSchema.parse(body);

    const supabase = getSupabaseServerClient();
    const { error } = await supabase.from('nutrition_goals').upsert(
      {
        user_id: user.id,
        name: 'default',
        energy_kcal_target: payload.calories,
        protein_g_target: payload.protein,
        carbs_g_target: payload.carbs,
        fat_g_target: payload.fat,
        fiber_g_target: payload.fiber
      },
      {
        onConflict: 'user_id,name'
      }
    );
    if (error) throw error;

    return NextResponse.json({ status: 'ok' });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
