import cors from 'cors';
import express from 'express';
import type { ZodTypeAny } from 'zod';

import { asyncHandler, handleError } from '../../shared/http';
import { logger } from '../../shared/logger';
import { healthHandler, requestLogger } from '../../shared/middleware';
import { insightsRequestSchema } from '../../shared/schemas';
import { supabaseServiceRole } from '../../shared/supabase';
import { buildInsightCacheKey, getCachedInsights, upsertInsight } from '../../shared/cache';
import {
  buildDailyBriefingPrompt,
  buildGenericInsightPrompt,
  buildNutritionCoachPrompt,
  buildTrainingFocusPrompt,
  buildWeeklyReviewPrompt,
  InsightResponseSchemas,
  describeTopic
} from '../../../lib/llm/prompts';
import { generateInsight } from '../../../lib/llm/vertex';
import type { InsightTopic } from '../../../lib/llm/types';

const app = express();
const port = process.env.PORT ?? '8080';

app.use(cors());
app.use(express.json());
app.use(requestLogger());

app.get('/health', healthHandler('llm'));

interface MetricsBundle {
  profile: Record<string, unknown> | null;
  nutritionGoals: Record<string, unknown> | null;
  dailyMetrics: Array<Record<string, any>>;
  macroCompliance: Array<Record<string, any>>;
  micronutrients: Array<Record<string, any>>;
  trainingLoadBalance: Array<Record<string, any>>;
  weightTrend: Array<Record<string, any>>;
  recentFoods: Array<Record<string, any>>;
  recentActivities: Array<Record<string, any>>;
}

interface InsightContext {
  user: Record<string, unknown>;
  range: { from: string; to: string };
  latestSnapshot: Record<string, unknown> | null;
  trends: Record<string, unknown>;
  weeklyMetrics: Array<Record<string, unknown>>;
  anomalies: string[];
  nutrition: {
    gapsVsGoals: Record<string, unknown>;
    inventoryOfFoods: Array<Record<string, unknown>>;
  };
  training: {
    zones: Record<string, unknown>;
    load: Record<string, unknown>;
    recoveryDeltas: Record<string, unknown>;
  };
  genericContext: Record<string, unknown>;
}

interface PromptConfig {
  prompt: string;
  schema: ZodTypeAny;
}

const DEFAULT_CONFIDENCE = 0.6;

app.post(
  '/insights',
  asyncHandler(async (req, res) => {
    const payload = insightsRequestSchema.parse(req.body);
    const { user_id: userId, from, to, topics } = payload;
    logger.info({ userId, from, to, topics }, 'insight generation request received');

    const metrics = await loadMetrics(userId, from, to);
    const context = prepareInsightContext(userId, from, to, metrics);
    const cacheKey = buildInsightCacheKey(userId, from, to, topics);
    const cachedSet = await getCachedInsights(userId, from, to, cacheKey, topics);

    const results: Array<{
      topic: InsightTopic;
      cached: boolean;
      summary: string;
      actions: string[];
      bullets: string[];
      confidence: number;
      references: Record<string, unknown>;
    }> = [];

    const processed = new Set<string>();

    if (cachedSet) {
      for (const [topic, row] of cachedSet.entries) {
        const metadata = (row.model_metadata ?? {}) as Record<string, unknown>;
        const highlights = toStringArray(metadata.highlights ?? metadata.bullets ?? []);
        const actions = toStringArray(row.actions);
        const confidence = typeof metadata.confidence === 'number' ? metadata.confidence : DEFAULT_CONFIDENCE;
        const references = (metadata.references ?? {}) as Record<string, unknown>;

        results.push({
          topic: topic as InsightTopic,
          cached: true,
          summary: row.summary,
          actions,
          bullets: highlights,
          confidence,
          references
        });
        processed.add(topic);
      }
    }

    for (const topic of topics) {
      if (processed.has(topic)) continue;

      const config = resolvePromptConfig(topic, context);
      if (!config) {
        logger.warn({ topic }, 'no prompt configuration found for topic');
        continue;
      }

      const parsed = await generateInsight(config.prompt, config.schema);
      const highlights = toStringArray(parsed.highlights ?? []);
      const references = (parsed.references ?? {}) as Record<string, unknown>;
      const actions = toStringArray(parsed.actions ?? []);
      const confidence = typeof parsed.confidence === 'number' ? parsed.confidence : DEFAULT_CONFIDENCE;

      await upsertInsight({
        userId,
        topic,
        from,
        to,
        summary: parsed.summary,
        actions,
        highlights,
        references,
        confidence,
        cacheKey
      });

      results.push({
        topic,
        cached: false,
        summary: parsed.summary,
        actions,
        bullets: highlights,
        confidence,
        references
      });
    }

    res.json({ data: results });
  })
);

async function loadMetrics(userId: string, from: string, to: string): Promise<MetricsBundle> {
  const supabase = supabaseServiceRole;
  const lookbackStart = computeLookbackDate(from, 14);
  const fromTimestamp = `${lookbackStart}T00:00:00Z`;
  const toTimestamp = `${to}T23:59:59Z`;

  const [
    dailyMetricsRes,
    macroRes,
    microRes,
    loadBalanceRes,
    weightTrendRes,
    profileRes,
    goalsRes,
    foodsRes,
    activitiesRes
  ] = await Promise.all([
    supabase
      .from('daily_metrics')
      .select('*')
      .eq('user_id', userId)
      .gte('metric_date', lookbackStart)
      .lte('metric_date', to),
    supabase
      .from('v_macro_compliance')
      .select('*')
      .eq('user_id', userId)
      .gte('date', lookbackStart)
      .lte('date', to),
    supabase
      .from('v_micronutrient_coverage')
      .select('*')
      .eq('user_id', userId)
      .gte('date', lookbackStart)
      .lte('date', to),
    supabase
      .from('v_training_load_balance')
      .select('*')
      .eq('user_id', userId)
      .gte('date', lookbackStart)
      .lte('date', to),
    supabase
      .from('v_weight_trend')
      .select('*')
      .eq('user_id', userId)
      .gte('date', lookbackStart)
      .lte('date', to),
    supabase
      .from('profiles')
      .select('user_id,sex,dob,height_cm,unit_pref,timezone')
      .eq('user_id', userId)
      .maybeSingle(),
    supabase.from('nutrition_goals').select('*').eq('user_id', userId).maybeSingle(),
    supabase
      .from('nutrition_entries')
      .select('entry_ts,food_name,calories,protein_g,carbs_g,fat_g')
      .eq('user_id', userId)
      .gte('entry_ts', fromTimestamp)
      .lte('entry_ts', toTimestamp)
      .order('entry_ts', { ascending: false })
      .limit(50),
    supabase
      .from('activities')
      .select('start_time,duration_s,avg_hr,max_hr,trimp,tss_est,sport')
      .eq('user_id', userId)
      .gte('start_time', fromTimestamp)
      .lte('start_time', toTimestamp)
      .order('start_time', { ascending: false })
      .limit(30)
  ]);

  if (dailyMetricsRes.error) throw dailyMetricsRes.error;
  if (macroRes.error) throw macroRes.error;
  if (microRes.error) throw microRes.error;
  if (loadBalanceRes.error) throw loadBalanceRes.error;
  if (weightTrendRes.error) throw weightTrendRes.error;
  if (profileRes.error && profileRes.status !== 406) throw profileRes.error;
  if (goalsRes.error && goalsRes.status !== 406) throw goalsRes.error;
  if (foodsRes.error) throw foodsRes.error;
  if (activitiesRes.error) throw activitiesRes.error;

  return {
    profile: profileRes.data ?? null,
    nutritionGoals: goalsRes.data ?? null,
    dailyMetrics: sortByDate(dailyMetricsRes.data ?? [], 'metric_date'),
    macroCompliance: macroRes.data ?? [],
    micronutrients: microRes.data ?? [],
    trainingLoadBalance: loadBalanceRes.data ?? [],
    weightTrend: sortByDate(weightTrendRes.data ?? [], weightTrendRes.data?.[0]?.metric_date ? 'metric_date' : 'date'),
    recentFoods: foodsRes.data ?? [],
    recentActivities: activitiesRes.data ?? []
  };
}

function prepareInsightContext(userId: string, from: string, to: string, data: MetricsBundle): InsightContext {
  const dailySeries = data.dailyMetrics;
  const weeklyMetrics = dailySeries.filter((row) => inRange(row.metric_date, from, to));
  const latestSnapshot = dailySeries.length ? dailySeries[dailySeries.length - 1] : null;
  const anomalies = detectAnomalies(weeklyMetrics);
  const trends = buildTrendSummaries(dailySeries, data.weightTrend);
  const nutrition = buildNutritionSummary(data, weeklyMetrics);
  const training = buildTrainingSummary(dailySeries, data.trainingLoadBalance, data.recentActivities);
  const userDescriptor = buildUserDescriptor(userId, data.profile, data.nutritionGoals);

  return {
    user: userDescriptor,
    range: { from, to },
    latestSnapshot,
    trends,
    weeklyMetrics,
    anomalies,
    nutrition,
    training,
    genericContext: {
      dailySnapshot: latestSnapshot,
      trends,
      weeklyMetrics,
      nutrition,
      training
    }
  };
}

const PROMPT_RESOLVERS: Record<string, (context: InsightContext) => PromptConfig> = {
  daily: (context) => ({
    prompt: buildDailyBriefingPrompt({
      user: context.user,
      range: context.range,
      metrics: context.latestSnapshot,
      trends: context.trends
    }),
    schema: InsightResponseSchemas.daily
  }),
  weekly: (context) => ({
    prompt: buildWeeklyReviewPrompt({
      user: context.user,
      range: context.range,
      metrics7d: context.weeklyMetrics,
      anomalies: context.anomalies
    }),
    schema: InsightResponseSchemas.weekly
  }),
  nutrition: (context) => ({
    prompt: buildNutritionCoachPrompt({
      user: context.user,
      range: context.range,
      gapsVsGoals: context.nutrition.gapsVsGoals,
      inventoryOfFoods: context.nutrition.inventoryOfFoods
    }),
    schema: InsightResponseSchemas.nutrition
  }),
  training: (context) => ({
    prompt: buildTrainingFocusPrompt({
      user: context.user,
      range: context.range,
      zones: context.training.zones,
      load: context.training.load,
      recoveryDeltas: context.training.recoveryDeltas
    }),
    schema: InsightResponseSchemas.training
  })
};

function resolvePromptConfig(topic: InsightTopic, context: InsightContext): PromptConfig {
  const resolver = PROMPT_RESOLVERS[topic];
  if (resolver) {
    return resolver(context);
  }

  return {
    prompt: buildGenericInsightPrompt({
      user: context.user,
      range: context.range,
      topic: describeTopic(topic),
      context: context.genericContext
    }),
    schema: InsightResponseSchemas.daily
  };
}

function buildUserDescriptor(
  userId: string,
  profile: Record<string, unknown> | null,
  goals: Record<string, unknown> | null
) {
  return {
    user_id: userId,
    sex: profile?.sex ?? null,
    date_of_birth: profile?.dob ?? null,
    height_cm: profile?.height_cm ?? null,
    unit_preference: profile?.unit_pref ?? null,
    timezone: profile?.timezone ?? null,
    nutrition_goals: goals ?? null
  };
}

function inRange(value: unknown, from: string, to: string) {
  if (typeof value !== 'string') return false;
  return value >= from && value <= to;
}

function computeLookbackDate(anchor: string, days: number) {
  const parsed = parseISODate(anchor);
  if (!parsed) return anchor;
  const lookback = new Date(parsed.getTime() - days * 86400000);
  return lookback.toISOString().slice(0, 10);
}

function parseISODate(value: string) {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function sortByDate<T extends Record<string, any>>(rows: T[], key: string) {
  return [...rows].sort((a, b) => {
    const aValue = String(a?.[key] ?? '');
    const bValue = String(b?.[key] ?? '');
    return aValue.localeCompare(bValue);
  });
}

function detectAnomalies(metrics: Array<Record<string, any>>) {
  if (!metrics.length) return [];
  const anomalies: string[] = [];
  const latest = metrics[metrics.length - 1];
  const prior = metrics.slice(0, -1);

  const avgSleep = average(metrics.map((m) => asNumber(m.sleep_minutes_total)));
  if (avgSleep && asNumber(latest.sleep_minutes_total) < avgSleep * 0.85) {
    anomalies.push('Sleep duration dropped more than 15% vs the weekly average.');
  }

  const avgLoad = average(metrics.map((m) => asNumber(m.training_load)));
  if (avgLoad && asNumber(latest.training_load) > avgLoad * 1.35) {
    anomalies.push('Training load spiked more than 35% vs the recent average.');
  }

  if (prior.length) {
    const restingBaseline = average(prior.map((m) => asNumber(m.resting_hr)));
    if (restingBaseline && asNumber(latest.resting_hr) - restingBaseline >= 5) {
      anomalies.push('Resting heart rate is elevated by ≥5 bpm vs baseline.');
    }

    const hrvBaseline = average(prior.map((m) => asNumber(m.hrv_rmssd)));
    if (hrvBaseline && hrvBaseline - asNumber(latest.hrv_rmssd) >= hrvBaseline * 0.2) {
      anomalies.push('HRV dropped more than 20% below the baseline.');
    }
  }

  return anomalies;
}

function buildTrendSummaries(dailySeries: Array<Record<string, any>>, weightTrend: Array<Record<string, any>>) {
  const recent = dailySeries.slice(-14);
  return {
    readiness_score: recent.map((row) => pick(row, ['metric_date', 'readiness_score'])),
    sleep_minutes_total: recent.map((row) => pick(row, ['metric_date', 'sleep_minutes_total'])),
    resting_hr: recent.map((row) => pick(row, ['metric_date', 'resting_hr'])),
    hrv_rmssd: recent.map((row) => pick(row, ['metric_date', 'hrv_rmssd'])),
    training_load: recent.map((row) => pick(row, ['metric_date', 'training_load'])),
    weight: weightTrend.slice(-14)
  };
}

function buildNutritionSummary(data: MetricsBundle, weeklyMetrics: Array<Record<string, any>>) {
  const averageCalories = average(weeklyMetrics.map((row) => asNumber(row.energy_burned_kcal)));
  return {
    gapsVsGoals: {
      macroCompliance: data.macroCompliance,
      micronutrients: data.micronutrients,
      nutritionGoals: data.nutritionGoals,
      averageDailyCalories: averageCalories,
      weeklyMetrics
    },
    inventoryOfFoods: dedupeFoods(data.recentFoods)
  };
}

function buildTrainingSummary(
  dailySeries: Array<Record<string, any>>,
  trainingLoadBalance: Array<Record<string, any>>,
  activities: Array<Record<string, any>>
) {
  const recent = dailySeries.slice(-14);
  const totals = activities.reduce(
    (acc, activity) => {
      const sport = (activity.sport as string | undefined) ?? 'unknown';
      const durationMinutes = asNumber(activity.duration_s) / 60;
      acc.totalDurationMinutes += durationMinutes;
      acc.bySport[sport] = (acc.bySport[sport] ?? 0) + durationMinutes;
      acc.sessions.push({
        start_time: activity.start_time,
        duration_minutes: round(durationMinutes),
        avg_hr: activity.avg_hr,
        trimp: activity.trimp,
        tss_est: activity.tss_est,
        sport
      });
      return acc;
    },
    { totalDurationMinutes: 0, bySport: {} as Record<string, number>, sessions: [] as Array<Record<string, unknown>> }
  );

  return {
    zones: {
      total_duration_minutes: round(totals.totalDurationMinutes),
      distribution_by_sport: totals.bySport,
      recent_sessions: totals.sessions.slice(0, 10)
    },
    load: {
      balance: trainingLoadBalance,
      rolling_training_load: recent.map((row) => pick(row, ['metric_date', 'training_load']))
    },
    recoveryDeltas: computeRecoveryDeltas(dailySeries)
  };
}

function computeRecoveryDeltas(series: Array<Record<string, any>>) {
  if (series.length < 2) {
    return {
      readiness_delta: null,
      hrv_delta: null,
      resting_hr_delta: null
    };
  }

  const sorted = series;
  const latest = sorted[sorted.length - 1];
  const baseline = sorted.slice(Math.max(0, sorted.length - 8), sorted.length - 1);

  return {
    readiness_delta: delta(asNumber(latest.readiness_score), baseline.map((row) => asNumber(row.readiness_score))),
    hrv_delta: delta(asNumber(latest.hrv_rmssd), baseline.map((row) => asNumber(row.hrv_rmssd))),
    resting_hr_delta: delta(asNumber(latest.resting_hr), baseline.map((row) => asNumber(row.resting_hr)))
  };
}

function delta(current: number | null, baselineValues: number[]) {
  if (current === null) return null;
  const baseline = average(baselineValues);
  if (baseline === null) return null;
  return round(current - baseline, 2);
}

function average(values: number[]) {
  const filtered = values.filter((value) => Number.isFinite(value));
  if (!filtered.length) return null;
  const total = filtered.reduce((sum, value) => sum + value, 0);
  return total / filtered.length;
}

function dedupeFoods(foods: Array<Record<string, any>>) {
  const seen = new Set<string>();
  const items: Array<Record<string, unknown>> = [];

  for (const entry of foods) {
    const name = typeof entry.food_name === 'string' ? entry.food_name.trim() : '';
    if (!name) continue;
    const key = name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    items.push({
      food_name: name,
      entry_ts: entry.entry_ts,
      calories: entry.calories,
      macros: {
        protein_g: entry.protein_g,
        carbs_g: entry.carbs_g,
        fat_g: entry.fat_g
      }
    });
    if (items.length >= 15) break;
  }

  return items;
}

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }
  return [];
}

function asNumber(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function pick<T extends Record<string, any>>(source: T, keys: [string, string]) {
  const [fromKey, toKey] = keys;
  return {
    date: source[fromKey] ?? source[toKey],
    value: source[toKey] ?? source[fromKey]
  };
}

function round(value: number, precision = 1) {
  const factor = 10 ** precision;
  return Math.round(value * factor) / factor;
}

app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  logger.error({ err }, 'Unhandled error in llm service');
  handleError(err, res);
});

export function start() {
  app.listen(port, () => {
    logger.info({ port }, 'llm service listening');
  });
}

if (require.main === module) {
  start();
}
