import { z } from 'zod';

export const nutritionEntrySchema = z.object({
  id: z.number().optional(),
  timestamp: z.coerce.date(),
  foodName: z.string().min(2),
  mealType: z.enum(['breakfast', 'lunch', 'dinner', 'snack', 'supplement']).optional(),
  calories: z.coerce.number().int().min(0).optional(),
  protein_g: z.coerce.number().min(0).optional(),
  carbs_g: z.coerce.number().min(0).optional(),
  fat_g: z.coerce.number().min(0).optional(),
  fiber_g: z.coerce.number().min(0).optional(),
  sugar_g: z.coerce.number().min(0).optional(),
  sat_fat_g: z.coerce.number().min(0).optional(),
  sodium_mg: z.coerce.number().min(0).optional(),
  potassium_mg: z.coerce.number().min(0).optional(),
  calcium_mg: z.coerce.number().min(0).optional(),
  iron_mg: z.coerce.number().min(0).optional(),
  vit_c_mg: z.coerce.number().min(0).optional(),
  vit_d_iu: z.coerce.number().min(0).optional(),
  notes: z.string().max(500).optional()
});

export const nutritionQuerySchema = z.object({
  date: z.string().optional()
});

export type NutritionEntryInput = z.infer<typeof nutritionEntrySchema>;
