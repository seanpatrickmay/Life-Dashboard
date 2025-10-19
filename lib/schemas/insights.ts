import { z } from 'zod';

export const insightTopicEnum = z.enum(['daily', 'weekly', 'nutrition', 'training', 'custom']);

export const insightsQuerySchema = z.object({
  from: z.string().optional(),
  to: z.string().optional(),
  topic: insightTopicEnum.optional()
});

export const generateInsightSchema = z.object({
  topic: insightTopicEnum,
  range: z.object({
    from: z.string(),
    to: z.string()
  }),
  userId: z.string().uuid().optional()
});
