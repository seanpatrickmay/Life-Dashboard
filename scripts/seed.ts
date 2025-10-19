#!/usr/bin/env tsx

import crypto from 'node:crypto';

import { getSupabaseServiceRoleClient } from '../lib/supabase';

interface SeedOptions {
  userId?: string;
  email?: string;
  days?: number;
}

const DEFAULT_DAYS = 14;

async function main() {
  const options: SeedOptions = {
    userId: process.env.SEED_USER_ID ?? undefined,
    email: process.env.SEED_EMAIL ?? undefined,
    days: process.env.SEED_DAYS ? Number.parseInt(process.env.SEED_DAYS, 10) : DEFAULT_DAYS
  };

  if (options.days && Number.isNaN(options.days)) {
    throw new Error(`Invalid SEED_DAYS value: ${process.env.SEED_DAYS}`);
  }

  const supabase = getSupabaseServiceRoleClient();
  const { userId, email } = await ensureUser(supabase, options);

  console.log(`Seeding data for ${email} (${userId})`);

  await upsertProfile(supabase, userId, email);
  await insertNutritionGoals(supabase, userId);
  await insertDailyMetrics(supabase, userId, options.days ?? DEFAULT_DAYS);
  await insertActivities(supabase, userId);
  await insertInsights(supabase, userId);

  console.log('Seed complete.');
}

async function ensureUser(supabase: ReturnType<typeof getSupabaseServiceRoleClient>, options: SeedOptions) {
  if (options.userId) {
    const { data, error } = await supabase.auth.admin.getUserById(options.userId);
    if (error) throw error;
    if (!data?.user) {
      throw new Error(`User with id ${options.userId} not found`);
    }
    return { userId: data.user.id, email: data.user.email ?? 'demo@example.com' };
  }

  const email = options.email ?? `demo+${Date.now()}@life-dashboard.local`;
  const tempPassword = crypto.randomUUID().replace(/-/g, '').slice(0, 16);
  const { data, error } = await supabase.auth.admin.createUser({
    email,
    password: tempPassword,
    email_confirm: true,
    user_metadata: { seed: true }
  });
  if (error) throw error;
  if (!data?.user) {
    throw new Error('Failed to create seed user');
  }
  return { userId: data.user.id, email: data.user.email ?? email };
}

async function upsertProfile(
  supabase: ReturnType<typeof getSupabaseServiceRoleClient>,
  userId: string,
  email: string
) {
  console.log(`Upserting profile for ${email}`);

  const { error } = await supabase.from('profiles').upsert(
    {
      id: userId,
      email,
      role: 'owner',
      default_unit_system: 'metric',
      timezone: 'America/New_York'
    },
    { onConflict: 'id' }
  );

  if (error) {
    throw error;
  }
}

async function insertNutritionGoals(supabase: ReturnType<typeof getSupabaseServiceRoleClient>, userId: string) {
  console.log('Inserting nutrition goals');
  const { error } = await supabase.from('nutrition_goals').upsert(
    {
      user_id: userId,
      name: 'default',
      energy_kcal_target: 2500,
      protein_g_target: 160,
      carbs_g_target: 320,
      fat_g_target: 80,
      fiber_g_target: 30,
      sodium_mg_limit: 2300,
      potassium_mg_target: 4000,
      calcium_mg_target: 1000,
      iron_mg_target: 12,
      vit_c_mg_target: 75,
      vit_d_iu_target: 600
    },
    { onConflict: 'user_id,name' }
  );
  if (error) throw error;
}

async function insertDailyMetrics(supabase: ReturnType<typeof getSupabaseServiceRoleClient>, userId: string, days: number) {
  console.log(`Generating ${days} days of daily metrics`);
  const now = new Date();
  const rows = [];

  for (let index = 0; index < days; index += 1) {
    const metricDate = new Date(now.getTime() - index * 86400000).toISOString().slice(0, 10);
    rows.push({
      user_id: userId,
      metric_date: metricDate,
      energy_burned_kcal: Math.round(2450 + randomInRange(-150, 180)),
      steps: Math.round(9500 + randomInRange(-1800, 2100)),
      sleep_minutes_total: Math.round(430 + randomInRange(-50, 60)),
      sleep_efficiency: Math.round(86 + randomInRange(-4, 5)),
      resting_hr: Math.round(55 + randomInRange(-3, 4)),
      hrv_rmssd: Math.round(72 + randomInRange(-6, 7)),
      stress_score: Number((18 + randomInRange(-4, 6)).toFixed(1)),
      training_load: Number((70 + randomInRange(-20, 28)).toFixed(1)),
      weight_kg: Number((72 + randomInRange(-0.4, 0.6)).toFixed(2))
    });
  }

  const { error } = await supabase.from('daily_metrics').upsert(rows, {
    onConflict: 'user_id,metric_date'
  });
  if (error) throw error;
}

async function insertActivities(supabase: ReturnType<typeof getSupabaseServiceRoleClient>, userId: string) {
  console.log('Creating synthetic activities');
  const baseDate = new Date();
  const activities = Array.from({ length: 6 }, (_value, index) => {
    const start = new Date(baseDate.getTime() - index * 86400000).toISOString();
    const durationSeconds = 45 * 60 + index * 120;
    return {
      user_id: userId,
      source: 'garmin',
      source_id: `demo-activity-${index + 1}`,
      name: index % 2 === 0 ? 'Endurance Run' : 'Tempo Session',
      sport_type: 'running',
      start_time: start,
      duration_s: durationSeconds,
      distance_m: 10000 + index * 350,
      avg_hr: Math.round(148 + randomInRange(-5, 6)),
      max_hr: Math.round(172 + randomInRange(-4, 5)),
      trimp: Number((68 + randomInRange(-10, 12)).toFixed(2)),
      tss_est: Number((75 + randomInRange(-12, 14)).toFixed(2))
    };
  });

  const { error } = await supabase
    .from('activities')
    .upsert(activities, { onConflict: 'user_id,source,source_id' });

  if (error) throw error;
}

async function insertInsights(supabase: ReturnType<typeof getSupabaseServiceRoleClient>, userId: string) {
  console.log('Generating mock insights');
  const nowIso = new Date().toISOString();
  const entries = [
    {
      topic: 'daily',
      summary: 'Recovery signals look strong—plan to hit the scheduled tempo run.',
      highlights: ['HRV trending +8% vs baseline', 'Resting HR down 3 bpm week-over-week'],
      actions: ['Complete 40min tempo at Zone 3', 'Extend cooldown with 10min easy jog'],
      confidence: 0.72,
      references: {
        readiness_score: 87,
        hrv_rmssd: 78,
        resting_hr: 53
      },
      range: recentRange(0)
    },
    {
      topic: 'weekly',
      summary: 'Overall load climbed smoothly with no major red flags—nutrition compliance dipped mid-week.',
      highlights: ['CTL +4 points vs prior week', 'Protein intake averaged 0.9g/lb (target 1.0g/lb)'],
      actions: ['Batch prep lunches to close protein gap', 'Keep Saturday ride in Zone 2 to maintain TSB >= 5'],
      confidence: 0.68,
      references: {
        ctl: 72,
        atl: 66,
        macro_compliance: {
          protein: 0.9,
          carbs: 1.03,
          fat: 0.95
        }
      },
      range: recentRange(7)
    }
  ];

  const { error } = await supabase.from('insights').upsert(
    entries.map((entry) => ({
      user_id: userId,
      topic: entry.topic,
      date_range: `[${entry.range.from},${entry.range.to}]`,
      summary: entry.summary,
      bullets: entry.highlights,
      actions: entry.actions,
      model_metadata: {
        highlights: entry.highlights,
        bullets: entry.highlights,
        references: entry.references,
        confidence: entry.confidence,
        mock: true
      },
      confidence: entry.confidence,
      created_at: nowIso
    })),
    { onConflict: 'user_id,topic,date_range' }
  );

  if (error) throw error;
}

function recentRange(offsetDays: number) {
  const toDate = new Date(Date.now() - offsetDays * 86400000);
  const fromDate = new Date(toDate.getTime() - 6 * 86400000);
  return {
    from: fromDate.toISOString().slice(0, 10),
    to: toDate.toISOString().slice(0, 10)
  };
}

function randomInRange(min: number, max: number) {
  return Math.random() * (max - min) + min;
}

main().catch((error) => {
  console.error('[seed] failed', error);
  process.exit(1);
});
