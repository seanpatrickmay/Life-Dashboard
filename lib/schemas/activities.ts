import { z } from 'zod';

export const activityQuerySchema = z.object({
  from: z.string().optional(),
  to: z.string().optional(),
  limit: z.coerce.number().min(1).max(200).optional(),
  page: z.coerce.number().min(1).optional()
});
