import type { z } from 'zod';

import {
  DailyBriefingSchema,
  InsightResponseSchemas,
  NutritionCoachSchema,
  TrainingFocusSchema,
  WeeklyReviewSchema
} from '@/lib/llm/prompts';

export type InsightTopic = 'daily' | 'weekly' | 'nutrition' | 'training' | 'custom';

export type DailyInsightResponse = z.infer<typeof DailyBriefingSchema>;
export type WeeklyInsightResponse = z.infer<typeof WeeklyReviewSchema>;
export type NutritionInsightResponse = z.infer<typeof NutritionCoachSchema>;
export type TrainingInsightResponse = z.infer<typeof TrainingFocusSchema>;
export type StandardInsightResponse =
  | DailyInsightResponse
  | WeeklyInsightResponse
  | NutritionInsightResponse
  | TrainingInsightResponse;

export const STANDARD_INSIGHT_SCHEMAS = InsightResponseSchemas;

export interface InsightPayload {
  topic: InsightTopic;
  summary: string;
  actions: string[];
  highlights: string[];
  confidence: number;
  references: Record<string, unknown>;
  referencedMetrics?: string[];
  range: {
    from: string;
    to: string;
  };
  metadata?: Record<string, unknown>;
}
