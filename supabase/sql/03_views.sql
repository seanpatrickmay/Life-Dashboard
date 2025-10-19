-- 03_views.sql
-- Analytics views for readiness, macro compliance, micronutrients, weight trends, and training load.

------------------------------------------------------------
-- v_daily_readiness
-- Readiness formula:
--   40% Sleep ratio vs 7-day baseline
--   30% HRV z-score vs 14-day baseline/std dev
--   20% Resting HR deviation (lower is better)
--   10% Prior-day load vs 7-day load baseline
------------------------------------------------------------
create or replace view public.v_daily_readiness as
with metrics as (
  select
    dm.user_id,
    dm.metric_date,
    dm.sleep_minutes_total,
    dm.resting_hr,
    dm.hrv_rmssd,
    dm.training_load,
    avg(dm.sleep_minutes_total) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 7 preceding and 1 preceding
    ) as sleep_baseline,
    avg(dm.resting_hr) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 14 preceding and 1 preceding
    ) as resting_hr_baseline,
    avg(dm.hrv_rmssd) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 14 preceding and 1 preceding
    ) as hrv_avg,
    stddev_samp(dm.hrv_rmssd) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 14 preceding and 1 preceding
    ) as hrv_std,
    avg(dm.training_load) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 7 preceding and 1 preceding
    ) as load_baseline,
    lag(dm.training_load) over (
      partition by dm.user_id
      order by dm.metric_date
    ) as prior_load
  from public.daily_metrics dm
),
scored as (
  select
    metrics.user_id,
    metrics.metric_date as date,
    metrics.sleep_minutes_total,
    metrics.resting_hr,
    metrics.hrv_rmssd,
    metrics.training_load,
    metrics.sleep_baseline,
    metrics.resting_hr_baseline,
    metrics.hrv_avg,
    metrics.hrv_std,
    metrics.load_baseline,
    metrics.prior_load,
    greatest(
      0,
      least(
        40,
        coalesce(metrics.sleep_minutes_total, 0)::numeric /
          nullif(coalesce(metrics.sleep_baseline, metrics.sleep_minutes_total, 1), 0) * 40 / 1.2
      )
    ) as sleep_component,
    greatest(
      0,
      least(
        30,
        15
        + coalesce(
            case
              when metrics.hrv_std is not null and metrics.hrv_std > 0
                then (metrics.hrv_rmssd - metrics.hrv_avg) / metrics.hrv_std
              else 0
            end,
            0
          ) * 10
      )
    ) as hrv_component,
    greatest(
      0,
      least(
        20,
        20
        - coalesce(
            case
              when metrics.resting_hr_baseline is not null and metrics.resting_hr_baseline > 0
                then (metrics.resting_hr - metrics.resting_hr_baseline) / metrics.resting_hr_baseline
              else 0
            end,
            0
          ) * 100
      )
    ) as resting_component,
    greatest(
      0,
      least(
        10,
        10
        - coalesce(
            case
              when metrics.load_baseline is not null and metrics.load_baseline > 0
                then (coalesce(metrics.prior_load, 0) / metrics.load_baseline) - 1
              else 0
            end,
            0
          ) * 10
      )
    ) as load_component
  from metrics
)
select
  scored.user_id,
  scored.date,
  round(
    greatest(
      0,
      least(
        100,
        coalesce(scored.sleep_component, 0)
        + coalesce(scored.hrv_component, 0)
        + coalesce(scored.resting_component, 0)
        + coalesce(scored.load_component, 0)
      )
    ),
    2
  ) as readiness
from scored;

comment on view public.v_daily_readiness is
  'Composite readiness score combining sleep ratio (40%), HRV z-score (30%), resting HR deviation (20%), and prior-day load (10%).';

------------------------------------------------------------
-- v_macro_compliance
------------------------------------------------------------
create or replace view public.v_macro_compliance as
with entries as (
  select
    ne.user_id,
    (ne.entry_ts at time zone coalesce(p.timezone, 'UTC'))::date as entry_date,
    sum(coalesce(ne.calories, 0)) as calories,
    sum(coalesce(ne.protein_g, 0)) as protein_g,
    sum(coalesce(ne.carbs_g, 0)) as carbs_g,
    sum(coalesce(ne.fat_g, 0)) as fat_g
  from public.nutrition_entries ne
  join public.profiles p on p.user_id = ne.user_id
  group by ne.user_id, entry_date
),
targets as (
  select
    ng.user_id,
    ng.calories,
    ng.protein_g,
    ng.carbs_g,
    ng.fat_g
  from public.nutrition_goals ng
)
select
  e.user_id,
  e.entry_date as date,
  round(coalesce(e.calories, 0)::numeric / nullif(targets.calories, 0), 4) as pct_cal,
  round(coalesce(e.protein_g, 0)::numeric / nullif(targets.protein_g, 0), 4) as pct_protein,
  round(coalesce(e.carbs_g, 0)::numeric / nullif(targets.carbs_g, 0), 4) as pct_carbs,
  round(coalesce(e.fat_g, 0)::numeric / nullif(targets.fat_g, 0), 4) as pct_fat
from entries e
left join targets on targets.user_id = e.user_id;

comment on view public.v_macro_compliance is
  'Daily macro intake vs current nutrition goals (expressed as ratios).';

------------------------------------------------------------
-- v_micronutrient_coverage
------------------------------------------------------------
create or replace view public.v_micronutrient_coverage as
with entries as (
  select
    ne.user_id,
    (ne.entry_ts at time zone coalesce(p.timezone, 'UTC'))::date as entry_date,
    sum(coalesce(ne.sodium_mg, 0)) as sodium_mg,
    sum(coalesce(ne.potassium_mg, 0)) as potassium_mg,
    sum(coalesce(ne.calcium_mg, 0)) as calcium_mg,
    sum(coalesce(ne.iron_mg, 0)) as iron_mg,
    sum(coalesce(ne.vit_c_mg, 0)) as vit_c_mg,
    sum(coalesce(ne.vit_d_IU, 0)) as vit_d_IU
  from public.nutrition_entries ne
  join public.profiles p on p.user_id = ne.user_id
  group by ne.user_id, entry_date
),
targets as (
  select
    ng.user_id,
    ng.sodium_mg,
    ng.potassium_mg,
    ng.calcium_mg,
    ng.iron_mg,
    ng.vit_c_mg,
    ng.vit_d_IU
  from public.nutrition_goals ng
)
select
  e.user_id,
  e.entry_date as date,
  jsonb_build_object(
    'sodium', round(coalesce(e.sodium_mg, 0)::numeric / nullif(targets.sodium_mg, 0), 4),
    'potassium', round(coalesce(e.potassium_mg, 0)::numeric / nullif(targets.potassium_mg, 0), 4),
    'calcium', round(coalesce(e.calcium_mg, 0)::numeric / nullif(targets.calcium_mg, 0), 4),
    'iron', round(coalesce(e.iron_mg, 0)::numeric / nullif(targets.iron_mg, 0), 4),
    'vit_c', round(coalesce(e.vit_c_mg, 0)::numeric / nullif(targets.vit_c_mg, 0), 4),
    'vit_d', round(coalesce(e.vit_d_IU, 0)::numeric / nullif(targets.vit_d_IU, 0), 4)
  ) as coverage
from entries e
left join targets on targets.user_id = e.user_id;

comment on view public.v_micronutrient_coverage is
  'Micronutrient intake ratios vs configured nutrition goals, returned as a JSON object.';

------------------------------------------------------------
-- v_weight_trend
------------------------------------------------------------
create or replace view public.v_weight_trend as
select
  dm.user_id,
  dm.metric_date as date,
  round(
    avg(dm.weight_kg) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 6 preceding and current row
    ),
    2
  ) as ema_7,
  round(
    regr_slope(
      dm.weight_kg,
      extract(epoch from dm.metric_date::timestamp)
    ) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 6 preceding and current row
    ),
    6
  ) as slope_7
from public.daily_metrics dm
where dm.weight_kg is not null;

comment on view public.v_weight_trend is
  'Seven-day exponential moving average (approximated via window average) and regression slope of weight.';

------------------------------------------------------------
-- v_training_load_balance
------------------------------------------------------------
create or replace view public.v_training_load_balance as
select
  dm.user_id,
  dm.metric_date as date,
  round(
    avg(dm.training_load) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 41 preceding and current row
    ),
    2
  ) as ctl,
  round(
    avg(dm.training_load) over (
      partition by dm.user_id
      order by dm.metric_date
      rows between 6 preceding and current row
    ),
    2
  ) as atl,
  round(
    coalesce(
      avg(dm.training_load) over (
        partition by dm.user_id
        order by dm.metric_date
        rows between 41 preceding and current row
      ),
      0
    )
    - coalesce(
      avg(dm.training_load) over (
        partition by dm.user_id
        order by dm.metric_date
        rows between 6 preceding and current row
      ),
      0
    ),
    2
  ) as tsb
from public.daily_metrics dm;

comment on view public.v_training_load_balance is
  'Chronic Training Load (42-day avg), Acute Training Load (7-day avg), and Training Stress Balance (CTL - ATL).';

