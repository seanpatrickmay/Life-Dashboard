-- Materialized analytics views for Life Dashboard
-- Use `supabase db push` after updating.

create view public.v_daily_readiness as
with baseline as (
  select
    dm.user_id,
    dm.metric_date,
    dm.sleep_minutes_total,
    dm.sleep_efficiency,
    dm.resting_hr,
    dm.hrv_rmssd,
    dm.training_load,
    avg(dm.sleep_minutes_total) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 13 preceding and 1 preceding
    ) as baseline_sleep_minutes,
    avg(dm.sleep_efficiency) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 13 preceding and 1 preceding
    ) as baseline_sleep_efficiency,
    avg(dm.resting_hr) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 27 preceding and 1 preceding
    ) as baseline_resting_hr,
    avg(dm.hrv_rmssd) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 27 preceding and 1 preceding
    ) as baseline_hrv,
    avg(dm.training_load) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 6 preceding and 1 preceding
    ) as baseline_training_load
  from public.daily_metrics dm
)
select
  b.user_id,
  b.metric_date,
  b.sleep_minutes_total,
  b.sleep_efficiency,
  b.resting_hr,
  b.hrv_rmssd,
  b.training_load,
  coalesce(b.baseline_sleep_minutes, b.sleep_minutes_total) as baseline_sleep_minutes,
  coalesce(b.baseline_sleep_efficiency, b.sleep_efficiency) as baseline_sleep_efficiency,
  coalesce(b.baseline_resting_hr, b.resting_hr) as baseline_resting_hr,
  coalesce(b.baseline_hrv, b.hrv_rmssd) as baseline_hrv,
  coalesce(b.baseline_training_load, b.training_load) as baseline_training_load,
  greatest(
    0,
    least(
      100,
      round(
        0.35 * (least(b.sleep_minutes_total / nullif(b.baseline_sleep_minutes, 0), 1.2) * 100) +
        0.25 * (least(b.sleep_efficiency / nullif(b.baseline_sleep_efficiency, 0), 1.1) * 100) +
        0.2 * (
          case
            when b.resting_hr is null or b.baseline_resting_hr is null then 60
            else (1 - greatest(-0.2, least(0.2, (b.resting_hr - b.baseline_resting_hr) / nullif(b.baseline_resting_hr, 0)))) * 100
          end
        ) +
        0.2 * (
          case
            when b.hrv_rmssd is null or b.baseline_hrv is null then 60
            else least((b.hrv_rmssd / nullif(b.baseline_hrv, 0)) * 100, 140)
          end
        ) -
        0.1 * greatest(0, coalesce(b.training_load - b.baseline_training_load, 0))
      , 2)
    )
  ) as readiness_score
from baseline b;

create view public.v_macro_compliance as
with entries as (
  select
    ne.user_id,
    (ne.entry_timestamp at time zone coalesce(p.timezone, 'America/New_York'))::date as entry_date,
    sum(coalesce(ne.calories, 0)) as calories,
    sum(coalesce(ne.protein_g, 0)) as protein_g,
    sum(coalesce(ne.carbs_g, 0)) as carbs_g,
    sum(coalesce(ne.fat_g, 0)) as fat_g,
    sum(coalesce(ne.fiber_g, 0)) as fiber_g
  from public.nutrition_entries ne
  join public.profiles p on p.id = ne.user_id
  group by ne.user_id, entry_date
),
targets as (
  select
    ng.user_id,
    ng.energy_kcal_target,
    ng.protein_g_target,
    ng.carbs_g_target,
    ng.fat_g_target,
    ng.fiber_g_target,
    row_number() over (partition by ng.user_id order by ng.updated_at desc) as rn
  from public.nutrition_goals ng
)
select
  e.user_id,
  e.entry_date,
  e.calories,
  e.protein_g,
  e.carbs_g,
  e.fat_g,
  e.fiber_g,
  t.energy_kcal_target,
  t.protein_g_target,
  t.carbs_g_target,
  t.fat_g_target,
  t.fiber_g_target,
  least(e.calories / nullif(t.energy_kcal_target, 0), 1.5) as calories_ratio,
  least(e.protein_g / nullif(t.protein_g_target, 0), 1.5) as protein_ratio,
  least(e.carbs_g / nullif(t.carbs_g_target, 0), 1.5) as carbs_ratio,
  least(e.fat_g / nullif(t.fat_g_target, 0), 1.5) as fat_ratio,
  least(e.fiber_g / nullif(t.fiber_g_target, 0), 1.5) as fiber_ratio
from entries e
left join targets t on t.user_id = e.user_id and t.rn = 1;

create view public.v_micronutrient_coverage as
with entries as (
  select
    ne.user_id,
    (ne.entry_timestamp at time zone coalesce(p.timezone, 'America/New_York'))::date as entry_date,
    sum(coalesce(ne.calcium_mg, 0)) as calcium_mg,
    sum(coalesce(ne.iron_mg, 0)) as iron_mg,
    sum(coalesce(ne.magnesium_mg, 0)) as magnesium_mg,
    sum(coalesce(ne.zinc_mg, 0)) as zinc_mg,
    sum(coalesce(ne.vit_a_mcg, 0)) as vit_a_mcg,
    sum(coalesce(ne.vit_c_mg, 0)) as vit_c_mg,
    sum(coalesce(ne.vit_d_iu, 0)) as vit_d_iu,
    sum(coalesce(ne.vit_e_mg, 0)) as vit_e_mg,
    sum(coalesce(ne.vit_k_mcg, 0)) as vit_k_mcg,
    sum(coalesce(ne.folate_mcg, 0)) as folate_mcg,
    sum(coalesce(ne.omega3_mg, 0)) as omega3_mg,
    sum(coalesce(ne.potassium_mg, 0)) as potassium_mg,
    sum(coalesce(ne.sodium_mg, 0)) as sodium_mg
  from public.nutrition_entries ne
  join public.profiles p on p.id = ne.user_id
  group by ne.user_id, entry_date
),
targets as (
  select
    ng.user_id,
    ng.calcium_mg_target,
    ng.iron_mg_target,
    ng.magnesium_mg_target,
    ng.zinc_mg_target,
    ng.vit_a_mcg_target,
    ng.vit_c_mg_target,
    ng.vit_d_iu_target,
    ng.vit_e_mg_target,
    ng.vit_k_mcg_target,
    ng.folate_mcg_target,
    ng.omega3_mg_target,
    ng.potassium_mg_target,
    ng.sodium_mg_limit,
    row_number() over (partition by ng.user_id order by ng.updated_at desc) as rn
  from public.nutrition_goals ng
)
select
  e.user_id,
  e.entry_date,
  e.calcium_mg,
  e.iron_mg,
  e.magnesium_mg,
  e.zinc_mg,
  e.vit_a_mcg,
  e.vit_c_mg,
  e.vit_d_iu,
  e.vit_e_mg,
  e.vit_k_mcg,
  e.folate_mcg,
  e.omega3_mg,
  e.potassium_mg,
  e.sodium_mg,
  t.calcium_mg_target,
  t.iron_mg_target,
  t.magnesium_mg_target,
  t.zinc_mg_target,
  t.vit_a_mcg_target,
  t.vit_c_mg_target,
  t.vit_d_iu_target,
  t.vit_e_mg_target,
  t.vit_k_mcg_target,
  t.folate_mcg_target,
  t.omega3_mg_target,
  t.potassium_mg_target,
  t.sodium_mg_limit,
  least(e.calcium_mg / nullif(t.calcium_mg_target, 0), 1.5) as calcium_ratio,
  least(e.iron_mg / nullif(t.iron_mg_target, 0), 1.5) as iron_ratio,
  least(e.magnesium_mg / nullif(t.magnesium_mg_target, 0), 1.5) as magnesium_ratio,
  least(e.zinc_mg / nullif(t.zinc_mg_target, 0), 1.5) as zinc_ratio,
  least(e.vit_a_mcg / nullif(t.vit_a_mcg_target, 0), 1.5) as vit_a_ratio,
  least(e.vit_c_mg / nullif(t.vit_c_mg_target, 0), 1.5) as vit_c_ratio,
  least(e.vit_d_iu / nullif(t.vit_d_iu_target, 0), 1.5) as vit_d_ratio,
  least(e.vit_e_mg / nullif(t.vit_e_mg_target, 0), 1.5) as vit_e_ratio,
  least(e.vit_k_mcg / nullif(t.vit_k_mcg_target, 0), 1.5) as vit_k_ratio,
  least(e.folate_mcg / nullif(t.folate_mcg_target, 0), 1.5) as folate_ratio,
  least(e.omega3_mg / nullif(t.omega3_mg_target, 0), 1.5) as omega3_ratio,
  least(e.potassium_mg / nullif(t.potassium_mg_target, 0), 1.5) as potassium_ratio,
  case
    when t.sodium_mg_limit is null or e.sodium_mg is null or e.sodium_mg = 0 then null
    else least(1.5, t.sodium_mg_limit / e.sodium_mg)
  end as sodium_ratio_inverse
from entries e
left join targets t on t.user_id = e.user_id and t.rn = 1;

create view public.v_weight_trend as
select
  dm.user_id,
  dm.metric_date,
  dm.weight_kg,
  avg(dm.weight_kg) over (
    partition by dm.user_id
    order by dm.metric_date
    rows between 6 preceding and current row
  ) as weight_ema_7,
  regr_slope(
    dm.weight_kg,
    extract(epoch from (dm.metric_date)::timestamp)
  ) over (
    partition by dm.user_id
    order by dm.metric_date
    rows between 6 preceding and current row
  ) as weight_slope_per_second
from public.daily_metrics dm
where dm.weight_kg is not null;

create view public.v_training_load_balance as
with loads as (
  select
    dm.user_id,
    dm.metric_date,
    dm.training_load,
    avg(dm.training_load) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 6 preceding and current row
    ) as atl, -- acute training load (~7 day)
    avg(dm.training_load) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 42 preceding and current row
    ) as ctl -- chronic training load (~6 week)
  from public.daily_metrics dm
)
select
  loads.user_id,
  loads.metric_date,
  loads.training_load,
  loads.atl,
  loads.ctl,
  (loads.ctl - loads.atl) as tsb -- training stress balance
from loads;
