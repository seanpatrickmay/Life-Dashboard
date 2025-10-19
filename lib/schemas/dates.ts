import { z } from 'zod';

export const dateParamSchema = z.object({
  date: z
    .string()
    .min(8)
    .refine((value) => !Number.isNaN(Date.parse(value)), 'Invalid date'),
  userId: z.string().uuid().optional()
});

export const rangeQuerySchema = z.object({
  from: z
    .string()
    .optional()
    .transform((value) => (value ? new Date(value) : undefined)),
  to: z
    .string()
    .optional()
    .transform((value) => (value ? new Date(value) : undefined))
});
