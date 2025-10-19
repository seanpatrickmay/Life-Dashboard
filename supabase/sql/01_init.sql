-- 01_init.sql
-- Base schema for Life Dashboard hybrid architecture.

create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

------------------------------------------------------------
-- profiles
------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique,
  sex text,
  dob date,
  height_cm integer,
  unit_pref text,
  timezone text default 'America/New_York'
);

------------------------------------------------------------
-- connections
------------------------------------------------------------
create table if not exists public.connections (
  id bigserial primary key,
  user_id uuid not null,
  provider text not null,
  status text not null default 'disconnected',
  access_token_encrypted bytea,
  refresh_token_encrypted bytea,
  scopes text[] default '{}',
  latest_sync_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

------------------------------------------------------------
-- raw_events
------------------------------------------------------------
create table if not exists public.raw_events (
  id bigserial primary key,
  user_id uuid not null,
  provider text not null,
  payload jsonb not null,
  received_at timestamptz not null default now()
);

------------------------------------------------------------
-- daily_metrics
------------------------------------------------------------
create table if not exists public.daily_metrics (
  id bigserial primary key,
  user_id uuid not null,
  metric_date date not null,
  energy_burned_kcal integer,
  steps integer,
  sleep_minutes_total integer,
  sleep_efficiency numeric(5,2),
  resting_hr integer,
  hrv_rmssd numeric(6,2),
  stress_score numeric(6,2),
  training_load numeric(8,2),
  weight_kg numeric(6,2),
  body_fat_pct numeric(5,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, metric_date)
);

------------------------------------------------------------
-- activities
------------------------------------------------------------
create table if not exists public.activities (
  id bigserial primary key,
  user_id uuid not null,
  source_id text,
  provider text not null,
  start_time timestamptz not null,
  duration_s integer,
  distance_m integer,
  avg_hr integer,
  max_hr integer,
  trimp numeric(8,2),
  tss_est numeric(8,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, provider, source_id)
);

------------------------------------------------------------
-- nutrition_entries
------------------------------------------------------------
create table if not exists public.nutrition_entries (
  id bigserial primary key,
  user_id uuid not null,
  entry_ts timestamptz not null,
  food_name text not null,
  calories integer,
  protein_g numeric(6,2),
  carbs_g numeric(6,2),
  fat_g numeric(6,2),
  fiber_g numeric(6,2),
  sugar_g numeric(6,2),
  sat_fat_g numeric(6,2),
  sodium_mg integer,
  potassium_mg integer,
  calcium_mg integer,
  iron_mg integer,
  vit_c_mg integer,
  vit_d_IU integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

------------------------------------------------------------
-- nutrition_goals
------------------------------------------------------------
create table if not exists public.nutrition_goals (
  id bigserial primary key,
  user_id uuid not null,
  calories integer,
  protein_g numeric(6,2),
  carbs_g numeric(6,2),
  fat_g numeric(6,2),
  fiber_g numeric(6,2),
  sodium_mg integer,
  potassium_mg integer,
  calcium_mg integer,
  iron_mg integer,
  vit_c_mg integer,
  vit_d_IU integer,
  updated_at timestamptz not null default now(),
  unique (user_id)
);

------------------------------------------------------------
-- insights
------------------------------------------------------------
create table if not exists public.insights (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  date_range daterange not null,
  topic text not null,
  summary text not null,
  actions jsonb default '[]'::jsonb,
  model_metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

------------------------------------------------------------
-- stripe_customers
------------------------------------------------------------
create table if not exists public.stripe_customers (
  id bigserial primary key,
  user_id uuid not null,
  stripe_customer_id text not null unique,
  created_at timestamptz not null default now()
);

------------------------------------------------------------
-- subscriptions
------------------------------------------------------------
create table if not exists public.subscriptions (
  id bigserial primary key,
  user_id uuid not null,
  stripe_subscription_id text not null unique,
  status text not null,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

------------------------------------------------------------
-- feature_flags
------------------------------------------------------------
create table if not exists public.feature_flags (
  id bigserial primary key,
  user_id uuid not null,
  key text not null,
  enabled boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, key)
);

------------------------------------------------------------
-- Foreign keys
------------------------------------------------------------
alter table public.profiles
  add constraint profiles_user_id_fkey
  foreign key (user_id)
  references auth.users (id)
  on delete cascade;

alter table public.connections
  add constraint connections_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.raw_events
  add constraint raw_events_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.daily_metrics
  add constraint daily_metrics_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.activities
  add constraint activities_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.nutrition_entries
  add constraint nutrition_entries_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.nutrition_goals
  add constraint nutrition_goals_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.insights
  add constraint insights_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.stripe_customers
  add constraint stripe_customers_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.subscriptions
  add constraint subscriptions_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

alter table public.feature_flags
  add constraint feature_flags_user_id_fkey
  foreign key (user_id)
  references public.profiles (user_id)
  on delete cascade;

------------------------------------------------------------
-- Indexes
------------------------------------------------------------
create index if not exists idx_profiles_user_id on public.profiles (user_id);
create index if not exists idx_connections_user_id_provider on public.connections (user_id, provider);
create index if not exists idx_raw_events_user on public.raw_events (user_id, received_at desc);
create index if not exists idx_daily_metrics_user_date on public.daily_metrics (user_id, metric_date);
create index if not exists idx_activities_user_start on public.activities (user_id, start_time desc);
create index if not exists idx_nutrition_entries_user_ts on public.nutrition_entries (user_id, entry_ts desc);
create index if not exists idx_insights_user_created on public.insights (user_id, created_at desc);
create index if not exists idx_subscriptions_user on public.subscriptions (user_id);
create index if not exists idx_feature_flags_user on public.feature_flags (user_id);

