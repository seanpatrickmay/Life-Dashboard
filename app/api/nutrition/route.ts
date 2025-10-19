import { NextResponse } from 'next/server';
import { z } from 'zod';

import { UnauthorizedError, requireAuthedUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';
import { nutritionEntrySchema } from '@/lib/schemas/nutrition';

export async function POST(request: Request) {
  try {
    const user = await requireAuthedUser();
    const body = await request.json();
    const payload = nutritionEntrySchema.parse(body);

    const supabase = getSupabaseServerClient();
    const { data, error } = await supabase
      .from('nutrition_entries')
      .insert({
        user_id: user.id,
        entry_timestamp: payload.timestamp.toISOString(),
        food_name: payload.foodName,
        meal_type: payload.mealType,
        calories: payload.calories,
        protein_g: payload.protein_g,
        carbs_g: payload.carbs_g,
        fat_g: payload.fat_g,
        fiber_g: payload.fiber_g,
        sugar_g: payload.sugar_g,
        sat_fat_g: payload.sat_fat_g,
        sodium_mg: payload.sodium_mg,
        potassium_mg: payload.potassium_mg,
        calcium_mg: payload.calcium_mg,
        iron_mg: payload.iron_mg,
        magnesium_mg: payload.magnesium_mg,
        zinc_mg: payload.zinc_mg,
        vit_a_mcg: payload.vit_a_mcg,
        vit_c_mg: payload.vit_c_mg,
        vit_d_iu: payload.vit_d_iu,
        vit_e_mg: payload.vit_e_mg,
        vit_k_mcg: payload.vit_k_mcg,
        folate_mcg: payload.folate_mcg,
        omega3_mg: payload.omega3_mg,
        notes: payload.notes
      })
      .select()
      .single();

    if (error) {
      throw error;
    }

    return NextResponse.json({ data }, { status: 201 });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}

export async function PATCH(request: Request) {
  try {
    const user = await requireAuthedUser();
    const body = await request.json();
    const payload = nutritionEntrySchema.extend({ id: nutritionEntrySchema.shape.id }).parse(body);

    if (!payload.id) {
      return NextResponse.json({ error: 'Missing id' }, { status: 400 });
    }

    const supabase = getSupabaseServerClient();
    const { data, error } = await supabase
      .from('nutrition_entries')
      .update({
        entry_timestamp: payload.timestamp.toISOString(),
        food_name: payload.foodName,
        meal_type: payload.mealType,
        calories: payload.calories,
        protein_g: payload.protein_g,
        carbs_g: payload.carbs_g,
        fat_g: payload.fat_g,
        fiber_g: payload.fiber_g,
        sugar_g: payload.sugar_g,
        sat_fat_g: payload.sat_fat_g,
        sodium_mg: payload.sodium_mg,
        potassium_mg: payload.potassium_mg,
        calcium_mg: payload.calcium_mg,
        iron_mg: payload.iron_mg,
        magnesium_mg: payload.magnesium_mg,
        zinc_mg: payload.zinc_mg,
        vit_a_mcg: payload.vit_a_mcg,
        vit_c_mg: payload.vit_c_mg,
        vit_d_iu: payload.vit_d_iu,
        vit_e_mg: payload.vit_e_mg,
        vit_k_mcg: payload.vit_k_mcg,
        folate_mcg: payload.folate_mcg,
        omega3_mg: payload.omega3_mg,
        notes: payload.notes,
        updated_at: new Date().toISOString()
      })
      .eq('id', payload.id)
      .eq('user_id', user.id)
      .select()
      .single();

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

export async function DELETE(request: Request) {
  try {
    const user = await requireAuthedUser();
    const { id } = z
      .object({
        id: z.coerce.number().int().positive()
      })
      .parse(await request.json());

    const supabase = getSupabaseServerClient();
    const { error } = await supabase
      .from('nutrition_entries')
      .delete()
      .eq('id', id)
      .eq('user_id', user.id);

    if (error) throw error;

    return NextResponse.json({ status: 'deleted' });
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      return NextResponse.json({ error: error.message }, { status: 401 });
    }

    console.error(error);
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
