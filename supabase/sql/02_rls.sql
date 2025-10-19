-- 02_rls.sql
-- Row Level Security policies enforcing tenant isolation by user_id.

------------------------------------------------------------
-- Enable RLS
------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.connections enable row level security;
alter table public.raw_events enable row level security;
alter table public.daily_metrics enable row level security;
alter table public.activities enable row level security;
alter table public.nutrition_entries enable row level security;
alter table public.nutrition_goals enable row level security;
alter table public.insights enable row level security;
alter table public.stripe_customers enable row level security;
alter table public.subscriptions enable row level security;
alter table public.feature_flags enable row level security;

------------------------------------------------------------
-- Helper condition
------------------------------------------------------------
-- All policies allow access if the caller is the owner (auth.uid()) or the service role.

------------------------------------------------------------
-- profiles
------------------------------------------------------------
create policy profiles_select on public.profiles
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy profiles_modify on public.profiles
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- connections
------------------------------------------------------------
create policy connections_select on public.connections
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy connections_modify on public.connections
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- raw_events
------------------------------------------------------------
create policy raw_events_select on public.raw_events
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy raw_events_modify on public.raw_events
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- daily_metrics
------------------------------------------------------------
create policy daily_metrics_select on public.daily_metrics
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy daily_metrics_modify on public.daily_metrics
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- activities
------------------------------------------------------------
create policy activities_select on public.activities
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy activities_modify on public.activities
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- nutrition_entries
------------------------------------------------------------
create policy nutrition_entries_select on public.nutrition_entries
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy nutrition_entries_modify on public.nutrition_entries
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- nutrition_goals
------------------------------------------------------------
create policy nutrition_goals_select on public.nutrition_goals
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy nutrition_goals_modify on public.nutrition_goals
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- insights
------------------------------------------------------------
create policy insights_select on public.insights
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy insights_modify on public.insights
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- stripe_customers
------------------------------------------------------------
create policy stripe_customers_select on public.stripe_customers
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy stripe_customers_modify on public.stripe_customers
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- subscriptions
------------------------------------------------------------
create policy subscriptions_select on public.subscriptions
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy subscriptions_modify on public.subscriptions
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

------------------------------------------------------------
-- feature_flags
------------------------------------------------------------
create policy feature_flags_select on public.feature_flags
  for select
  using (auth.uid() = user_id or auth.role() = 'service_role');

create policy feature_flags_modify on public.feature_flags
  for all
  using (auth.uid() = user_id or auth.role() = 'service_role')
  with check (auth.uid() = user_id or auth.role() = 'service_role');

