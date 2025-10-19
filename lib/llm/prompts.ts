import { z } from 'zod';

const JSON_FORMAT_SPEC = `Respond ONLY with valid JSON (no code fences) that matches:
{
  "summary": string,
  "highlights": string[],
  "actions": string[],
  "confidence": number,    // between 0 and 1 inclusive
  "references": {          // map metric identifiers to brief evidence strings or objects
    "<metric_key>": string | number | boolean | object | string[]
  }
}`;

const BaseInsightSchema = z.object({
  summary: z.string().min(1),
  highlights: z.array(z.string()).default([]),
  actions: z.array(z.string()).default([]),
  confidence: z.number().min(0).max(1),
  references: z.record(z.any()).default({})
});

export const DailyBriefingSchema = BaseInsightSchema;
export const WeeklyReviewSchema = BaseInsightSchema;
export const NutritionCoachSchema = BaseInsightSchema;
export const TrainingFocusSchema = BaseInsightSchema;

export const InsightResponseSchemas = {
  daily: DailyBriefingSchema,
  weekly: WeeklyReviewSchema,
  nutrition: NutritionCoachSchema,
  training: TrainingFocusSchema
} as const;

export type DailyBriefingOutput = z.infer<typeof DailyBriefingSchema>;
export type WeeklyReviewOutput = z.infer<typeof WeeklyReviewSchema>;
export type NutritionCoachOutput = z.infer<typeof NutritionCoachSchema>;
export type TrainingFocusOutput = z.infer<typeof TrainingFocusSchema>;

export interface PromptRange {
  from: string;
  to: string;
}

export interface DailyBriefingPromptInput {
  user: Record<string, unknown>;
  range: PromptRange;
  metrics: Record<string, unknown> | null;
  trends: Record<string, unknown>;
}

export interface WeeklyReviewPromptInput {
  user: Record<string, unknown>;
  range: PromptRange;
  metrics7d: Array<Record<string, unknown>>;
  anomalies: string[];
}

export interface NutritionCoachPromptInput {
  user: Record<string, unknown>;
  range: PromptRange;
  gapsVsGoals: Record<string, unknown>;
  inventoryOfFoods?: Array<Record<string, unknown>>;
}

export interface TrainingFocusPromptInput {
  user: Record<string, unknown>;
  range: PromptRange;
  zones: Record<string, unknown>;
  load: Record<string, unknown>;
  recoveryDeltas: Record<string, unknown>;
}

const TITLE_CASE: Record<string, string> = {
  daily: 'Daily Briefing',
  weekly: 'Weekly Review',
  nutrition: 'Nutrition Coaching',
  training: 'Training Focus'
};

function formatSection(title: string, data: unknown) {
  return `${title}:\n${JSON.stringify(data ?? null, null, 2)}`;
}

export function buildDailyBriefingPrompt(input: DailyBriefingPromptInput) {
  return [
    'DAILY_BRIEFING REQUEST',
    'You are an evidence-based endurance coach. Provide a concise morning briefing for the athlete.',
    `Date range: ${input.range.from} → ${input.range.to}`,
    JSON_FORMAT_SPEC,
    'Focus on linking each highlight to objective metrics. Suggest a maximum of three actions.',
    formatSection('User context', input.user),
    formatSection('Key daily metrics', input.metrics),
    formatSection('Recent trend snapshots', input.trends)
  ].join('\n\n');
}

export function buildWeeklyReviewPrompt(input: WeeklyReviewPromptInput) {
  return [
    'WEEKLY_REVIEW REQUEST',
    'Summarise the past 7 days with emphasis on momentum, regressions, and any anomalies that need follow-up.',
    `Date range: ${input.range.from} → ${input.range.to}`,
    JSON_FORMAT_SPEC,
    'Compare against the prior period when useful. Explain why each recommendation matters.',
    formatSection('User context', input.user),
    formatSection('7-day metric roll-up', input.metrics7d),
    formatSection('Detected anomalies', input.anomalies)
  ].join('\n\n');
}

export function buildNutritionCoachPrompt(input: NutritionCoachPromptInput) {
  return [
    'NUTRITION_COACH REQUEST',
    'Evaluate nutrient intake vs. goals, spot the biggest gaps, and suggest practical food swaps using available foods when possible.',
    `Date range: ${input.range.from} → ${input.range.to}`,
    JSON_FORMAT_SPEC,
    'Keep tone supportive and avoid medical claims. Highlight the top two interventions.',
    formatSection('User context', input.user),
    formatSection('Gaps vs. goals', input.gapsVsGoals),
    formatSection('Current food inventory', input.inventoryOfFoods ?? [])
  ].join('\n\n');
}

export function buildTrainingFocusPrompt(input: TrainingFocusPromptInput) {
  return [
    'TRAINING_FOCUS REQUEST',
    'Review recent training intensity distribution, load, and recovery markers to advise on the coming block.',
    `Date range: ${input.range.from} → ${input.range.to}`,
    JSON_FORMAT_SPEC,
    'Flag warning signs (e.g., suppressed HRV, elevated resting HR) and adjust specific sessions.',
    formatSection('User context', input.user),
    formatSection('Intensity / zone distribution', input.zones),
    formatSection('Training load summary', input.load),
    formatSection('Recovery deltas', input.recoveryDeltas)
  ].join('\n\n');
}

export interface GenericPromptInput {
  user: Record<string, unknown>;
  range: PromptRange;
  topic: string;
  context: Record<string, unknown>;
}

export function buildGenericInsightPrompt(input: GenericPromptInput) {
  return [
    `${input.topic.toUpperCase()} REQUEST`,
    'Provide a concise coaching insight grounded in the supplied context.',
    `Date range: ${input.range.from} → ${input.range.to}`,
    JSON_FORMAT_SPEC,
    formatSection('User context', input.user),
    formatSection('Supporting context', input.context)
  ].join('\n\n');
}

export type InsightPromptBuilderInput =
  | DailyBriefingPromptInput
  | WeeklyReviewPromptInput
  | NutritionCoachPromptInput
  | TrainingFocusPromptInput
  | GenericPromptInput;

export type InsightPromptBuilder = (input: InsightPromptBuilderInput) => string;

export const InsightPromptBuilders = {
  daily: buildDailyBriefingPrompt,
  weekly: buildWeeklyReviewPrompt,
  nutrition: buildNutritionCoachPrompt,
  training: buildTrainingFocusPrompt
} as const;

export function describeTopic(topic: string) {
  return TITLE_CASE[topic] ?? topic;
}
