-- Row Level Security policies

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
alter table public.usage_records enable row level security;
alter table public.api_keys enable row level security;
alter table public.feature_flags enable row level security;
alter table public.audit_logs enable row level security;

create policy "Users can view own profile" on public.profiles
  for select using (auth.uid() = id);

create policy "Users can update own profile" on public.profiles
  for update using (auth.uid() = id);

create policy "Service role upserts profiles" on public.profiles
  for insert with check (auth.role() = 'service_role');

create policy "Users manage own connections" on public.connections
  for select using (auth.uid() = user_id);

create policy "Users insert own connections" on public.connections
  for insert with check (auth.uid() = user_id);

create policy "Users update own connections" on public.connections
  for update using (auth.uid() = user_id);

create policy "Service role manages connections" on public.connections
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Users view raw events" on public.raw_events
  for select using (auth.uid() = user_id);

create policy "Service role inserts raw events" on public.raw_events
  for insert with check (auth.role() = 'service_role');

create policy "Users view daily metrics" on public.daily_metrics
  for select using (auth.uid() = user_id);

create policy "Service role upserts daily metrics" on public.daily_metrics
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Users view activities" on public.activities
  for select using (auth.uid() = user_id);

create policy "Users insert activities" on public.activities
  for insert with check (auth.uid() = user_id);

create policy "Users update activities" on public.activities
  for update using (auth.uid() = user_id);

create policy "Service role manages activities" on public.activities
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Users manage nutrition entries" on public.nutrition_entries
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users manage nutrition goals" on public.nutrition_goals
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users view insights" on public.insights
  for select using (auth.uid() = user_id);

create policy "Service role inserts insights" on public.insights
  for insert with check (auth.role() = 'service_role');

create policy "Users view stripe customer" on public.stripe_customers
  for select using (auth.uid() = user_id);

create policy "Service role manages stripe customer" on public.stripe_customers
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Users view subscriptions" on public.subscriptions
  for select using (auth.uid() = user_id);

create policy "Service role manages subscriptions" on public.subscriptions
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Users view usage records" on public.usage_records
  for select using (auth.uid() = user_id);

create policy "Service role manages usage records" on public.usage_records
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

create policy "Owners manage api keys" on public.api_keys
  using (
    auth.role() = 'service_role'
    or exists (
      select 1
      from public.profiles p
      where p.id = auth.uid() and p.role = 'owner'
    )
  )
  with check (
    auth.role() = 'service_role'
    or exists (
      select 1
      from public.profiles p
      where p.id = auth.uid() and p.role = 'owner'
    )
  );

create policy "Feature flags readable to everyone" on public.feature_flags
  for select using (true);

create policy "Owners manage feature flags" on public.feature_flags
  using (
    auth.role() = 'service_role'
    or exists (
      select 1
      from public.profiles p
      where p.id = auth.uid() and p.role = 'owner'
    )
  )
  with check (
    auth.role() = 'service_role'
    or exists (
      select 1
      from public.profiles p
      where p.id = auth.uid() and p.role = 'owner'
    )
  );

create policy "Audit logs readable by owners" on public.audit_logs
  for select using (
    auth.role() = 'service_role'
    or exists (
      select 1
      from public.profiles p
      where p.id = auth.uid() and p.role = 'owner'
    )
  );

create policy "Service role inserts audit logs" on public.audit_logs
  for insert with check (auth.role() = 'service_role');
