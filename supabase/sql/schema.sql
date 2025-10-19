-- Schema definition for Life Dashboard
-- Run with: supabase db push --file supabase/sql/schema.sql

create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users on delete cascade,
  email text,
  full_name text,
  role text not null default 'member' check (role in ('owner', 'member')),
  sex text check (sex in ('male', 'female', 'other')),
  date_of_birth date,
  height_cm numeric(5,2),
  baseline_activity_level text check (baseline_activity_level in ('sedentary','lightly_active','moderately_active','very_active','athlete')),
  default_unit_system text not null default 'metric' check (default_unit_system in ('metric','imperial')),
  timezone text not null default 'America/New_York',
  maintenance_calories_est numeric(6,1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index on public.profiles (role);

create table if not exists public.connections (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  external_user_id text,
  provider text not null check (provider in ('garmin','withings','manual')),
  status text not null default 'disconnected' check (status in ('connected','paused','revoked','disconnected','error')),
  scopes text[] default '{}',
  access_token_encrypted bytea,
  refresh_token_encrypted bytea,
  expires_at timestamptz,
  latest_sync_at timestamptz,
  settings jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index on public.connections (user_id, provider);
create index on public.connections (external_user_id, provider);

create table if not exists public.raw_events (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  provider text not null check (provider in ('garmin','withings','manual')),
  event_type text not null,
  event_timestamp timestamptz,
  payload jsonb not null,
  received_at timestamptz not null default now()
);

create index on public.raw_events (user_id, provider);
create index on public.raw_events (received_at);

create table if not exists public.daily_metrics (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  metric_date date not null,
  energy_burned_kcal numeric(8,2),
  steps integer,
  sleep_minutes_total integer,
  sleep_efficiency numeric(5,2),
  resting_hr numeric(5,2),
  hrv_rmssd numeric(6,2),
  stress_score numeric(5,2),
  training_load numeric(8,2),
  weight_kg numeric(6,2),
  body_fat_pct numeric(5,2),
  readiness_score numeric(5,2),
  macros jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, metric_date)
);

create index on public.daily_metrics (user_id, metric_date);

create table if not exists public.activities (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  source text not null check (source in ('garmin','withings','manual')),
  source_id text,
  name text,
  sport_type text,
  start_time timestamptz not null,
  duration_s integer,
  distance_m numeric(8,2),
  avg_hr numeric(5,2),
  max_hr numeric(5,2),
  trimp numeric(6,2),
  tss_est numeric(6,2),
  calories numeric(7,2),
  data jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, source, source_id)
);

create index on public.activities using gin (data);
create index on public.activities (user_id, start_time);

create table if not exists public.nutrition_entries (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  entry_timestamp timestamptz not null,
  food_name text not null,
  meal_type text check (meal_type in ('breakfast','lunch','dinner','snack','supplement')),
  calories integer,
  protein_g numeric(6,2),
  carbs_g numeric(6,2),
  fat_g numeric(6,2),
  fiber_g numeric(6,2),
  sugar_g numeric(6,2),
  sat_fat_g numeric(6,2),
  sodium_mg numeric(8,2),
  potassium_mg numeric(8,2),
  calcium_mg numeric(8,2),
  iron_mg numeric(8,2),
  magnesium_mg numeric(8,2),
  zinc_mg numeric(8,2),
  vit_a_mcg numeric(8,2),
  vit_c_mg numeric(8,2),
  vit_d_iu numeric(8,2),
  vit_e_mg numeric(8,2),
  vit_k_mcg numeric(8,2),
  folate_mcg numeric(8,2),
  omega3_mg numeric(8,2),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index on public.nutrition_entries (user_id, entry_timestamp);

create table if not exists public.nutrition_goals (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  name text default 'default',
  energy_kcal_target integer,
  protein_g_target numeric(6,2),
  carbs_g_target numeric(6,2),
  fat_g_target numeric(6,2),
  fiber_g_target numeric(6,2),
  sugar_g_limit numeric(6,2),
  sat_fat_g_limit numeric(6,2),
  sodium_mg_limit numeric(8,2),
  potassium_mg_target numeric(8,2),
  calcium_mg_target numeric(8,2),
  iron_mg_target numeric(8,2),
  magnesium_mg_target numeric(8,2),
  zinc_mg_target numeric(8,2),
  vit_a_mcg_target numeric(8,2),
  vit_c_mg_target numeric(8,2),
  vit_d_iu_target numeric(8,2),
  vit_e_mg_target numeric(8,2),
  vit_k_mcg_target numeric(8,2),
  folate_mcg_target numeric(8,2),
  omega3_mg_target numeric(8,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);

create index on public.nutrition_goals (user_id);

create table if not exists public.insights (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  topic text not null check (topic in ('daily','weekly','nutrition','training','custom')),
  date_range daterange not null,
  summary text not null,
  bullets jsonb default '[]'::jsonb,
  actions jsonb default '[]'::jsonb,
  model_metadata jsonb,
  confidence numeric(3,2),
  created_at timestamptz not null default now()
);

create index on public.insights using gist (date_range);
create index on public.insights (user_id, created_at desc);

create table if not exists public.stripe_customers (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  customer_id text not null,
  created_at timestamptz not null default now(),
  unique (customer_id),
  unique (user_id)
);

create table if not exists public.subscriptions (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  stripe_subscription_id text not null,
  status text not null check (status in ('trialing','active','past_due','canceled','incomplete','incomplete_expired','unpaid')),
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at timestamptz,
  canceled_at timestamptz,
  price_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (stripe_subscription_id)
);

create index on public.subscriptions (user_id);

create table if not exists public.usage_records (
  id bigserial primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  feature_code text not null,
  period_start date not null,
  period_end date not null,
  usage_count integer not null default 0,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (user_id, feature_code, period_start, period_end)
);

create index on public.usage_records (user_id, feature_code);

create table if not exists public.api_keys (
  id bigserial primary key,
  name text not null,
  key_hash text not null,
  created_by uuid references public.profiles(id),
  expires_at timestamptz,
  last_used_at timestamptz,
  created_at timestamptz not null default now(),
  constraints jsonb default '{}'::jsonb
);

create unique index on public.api_keys (key_hash);

create table if not exists public.feature_flags (
  key text primary key,
  description text,
  is_active boolean not null default false,
  rollout jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.audit_logs (
  id bigserial primary key,
  actor_user_id uuid references public.profiles(id),
  target_user_id uuid references public.profiles(id),
  action text not null,
  resource_type text,
  resource_id text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index on public.audit_logs (actor_user_id, created_at desc);
