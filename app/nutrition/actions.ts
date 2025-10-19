'use server';

import { revalidatePath } from 'next/cache';

import { withRLS, requireAuthedUser } from '@/lib/auth';
import { nutritionEntrySchema } from '@/lib/schemas/nutrition';
import type { NutritionEntryInput } from '@/lib/schemas/nutrition';
import { z } from 'zod';

const goalsSchema = z.object({
  calories: z.number().optional(),
  protein: z.number().optional(),
  carbs: z.number().optional(),
  fat: z.number().optional(),
  fiber: z.number().optional()
});

export async function createNutritionEntryAction(input: NutritionEntryInput) {
  const user = await requireAuthedUser();
  const parsed = nutritionEntrySchema.parse(input);

  await withRLS(async (client) => {
    const { error } = await client.from('nutrition_entries').insert({
      user_id: user.id,
      entry_timestamp: parsed.timestamp.toISOString(),
      food_name: parsed.foodName,
      meal_type: parsed.mealType,
      calories: parsed.calories,
      protein_g: parsed.protein_g,
      carbs_g: parsed.carbs_g,
      fat_g: parsed.fat_g,
      fiber_g: parsed.fiber_g,
      sugar_g: parsed.sugar_g,
      sat_fat_g: parsed.sat_fat_g,
      sodium_mg: parsed.sodium_mg,
      potassium_mg: parsed.potassium_mg,
      calcium_mg: parsed.calcium_mg,
      iron_mg: parsed.iron_mg,
      vit_c_mg: parsed.vit_c_mg,
      vit_d_IU: parsed.vit_d_iu,
      notes: parsed.notes
    });
    if (error) throw error;
  });

  revalidatePath('/nutrition');
}

export async function updateNutritionEntryAction(input: NutritionEntryInput & { id: number }) {
  const user = await requireAuthedUser();
  const parsed = nutritionEntrySchema.extend({ id: z.number() }).parse(input);

  await withRLS(async (client) => {
    const { error } = await client
      .from('nutrition_entries')
      .update({
        entry_timestamp: parsed.timestamp.toISOString(),
        food_name: parsed.foodName,
        meal_type: parsed.mealType,
        calories: parsed.calories,
        protein_g: parsed.protein_g,
        carbs_g: parsed.carbs_g,
        fat_g: parsed.fat_g,
        fiber_g: parsed.fiber_g,
        sugar_g: parsed.sugar_g,
        sat_fat_g: parsed.sat_fat_g,
        sodium_mg: parsed.sodium_mg,
        potassium_mg: parsed.potassium_mg,
        calcium_mg: parsed.calcium_mg,
        iron_mg: parsed.iron_mg,
        vit_c_mg: parsed.vit_c_mg,
        vit_d_IU: parsed.vit_d_iu,
        notes: parsed.notes
      })
      .eq('id', parsed.id)
      .eq('user_id', user.id);
    if (error) throw error;
  });

  revalidatePath('/nutrition');
}

export async function deleteNutritionEntryAction(id: number) {
  const user = await requireAuthedUser();

  await withRLS(async (client) => {
    const { error } = await client.from('nutrition_entries').delete().eq('id', id).eq('user_id', user.id);
    if (error) throw error;
  });

  revalidatePath('/nutrition');
}

export async function updateNutritionGoalsAction(input: { calories?: number; protein?: number; carbs?: number; fat?: number; fiber?: number }) {
  const user = await requireAuthedUser();
  const parsed = goalsSchema.parse(input);

  await withRLS(async (client) => {
    const { error } = await client.from('nutrition_goals').upsert(
      {
        user_id: user.id,
        calories: parsed.calories,
        protein_g: parsed.protein,
        carbs_g: parsed.carbs,
        fat_g: parsed.fat,
        fiber_g: parsed.fiber,
        updated_at: new Date().toISOString()
      },
      {
        onConflict: 'user_id'
      }
    );
    if (error) throw error;
  });

  revalidatePath('/nutrition');
}
