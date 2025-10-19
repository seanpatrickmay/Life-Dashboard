import { z } from 'zod';

export const recomputeRequestSchema = z.object({
  date: z
    .string()
    .optional()
    .refine((value) => !value || !Number.isNaN(Date.parse(value)), {
      message: 'date must be a valid ISO string'
    })
});

export const backfillRequestSchema = z.object({
  provider: z.enum(['garmin', 'withings']),
  days: z
    .string()
    .or(z.number())
    .transform((value) => Number(value))
    .refine((value) => Number.isInteger(value) && value > 0 && value <= 365, {
      message: 'days must be an integer between 1 and 365'
    }),
  userId: z.string().uuid().optional()
});

export const insightsRequestSchema = z.object({
  user_id: z.string().uuid(),
  from: z.string().refine((value) => !Number.isNaN(Date.parse(value)), {
    message: 'from must be a valid ISO date'
  }),
  to: z.string().refine((value) => !Number.isNaN(Date.parse(value)), {
    message: 'to must be a valid ISO date'
  }),
  topics: z.array(z.enum(['daily', 'weekly', 'nutrition', 'training', 'custom'])).nonempty()
});
