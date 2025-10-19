import { redirect } from 'next/navigation';

import { LLMInsightCard } from '@/components/LLMInsightCard';
import { MetricCard } from '@/components/MetricCard';
import { ProgressRing } from '@/components/ProgressRing';
import { TrendLine } from '@/components/TrendLine';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getCurrentUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';

export default async function DashboardPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login');
  }

  const supabase = getSupabaseServerClient();
  const today = new Date().toISOString().slice(0, 10);

  const [{ data: readiness }, { data: weightTrend }, { data: latestInsight }] = await Promise.all([
    supabase
      .from('v_daily_readiness')
      .select('*')
      .eq('user_id', user.id)
      .eq('metric_date', today)
      .maybeSingle(),
    supabase
      .from('v_weight_trend')
      .select('metric_date, weight_kg, weight_ema_7')
      .eq('user_id', user.id)
      .order('metric_date', { ascending: true }),
    supabase
      .from('insights')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()
  ]);

  const latestReady = readiness ?? null;
  const weights = (weightTrend ?? []).map((row) => Number(row.weight_ema_7 ?? row.weight_kg ?? 0));

  return (
    <div className="space-y-6 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Today</h1>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Readiness"
          value={latestReady?.readiness_score ? latestReady.readiness_score.toString() : '—'}
          unit="score"
          trend={
            latestReady?.baseline_sleep_minutes
              ? `${Math.round(
                  ((latestReady.sleep_minutes_total ?? 0) / (latestReady.baseline_sleep_minutes ?? 1)) * 100
                )}% sleep`
              : 'baseline pending'
          }
          status={determineStatus(latestReady?.readiness_score)}
          description="Composite of sleep, recovery, and load"
        />
        <MetricCard
          title="Sleep"
          value={formatMinutes(latestReady?.sleep_minutes_total)}
          unit="hrs"
          trend={`${latestReady?.sleep_efficiency ?? '—'}% efficiency`}
          description="Previous night duration"
        />
        <MetricCard
          title="Resting HR"
          value={latestReady?.resting_hr ? latestReady.resting_hr.toFixed(0) : '—'}
          unit="bpm"
          trend={
            latestReady?.baseline_resting_hr
              ? diffString(latestReady.resting_hr, latestReady.baseline_resting_hr)
              : 'baseline pending'
          }
          status={determineStatus(latestReady?.resting_hr, true)}
          description="Morning measurement"
        />
        <MetricCard
          title="Training load"
          value={latestReady?.training_load ? latestReady.training_load.toFixed(0) : '—'}
          unit="pts"
          trend={latestReady?.baseline_training_load ? `vs ${Math.round(latestReady.baseline_training_load)}` : '—'}
          description="Past 24h load"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Weight trend</CardTitle>
          </CardHeader>
          <CardContent>
            <TrendLine values={weights} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recovery balance</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center py-6">
            <ProgressRing value={latestReady?.readiness_score ?? 0} label="Readiness" />
          </CardContent>
        </Card>
      </div>

      {latestInsight ? (
        <LLMInsightCard
          title="Today’s Coaching"
          summary={latestInsight.summary}
          bullets={((latestInsight.model_metadata as any)?.bullets ?? []) as string[]}
          actions={(latestInsight.actions ?? []) as string[]}
          confidence={Number((latestInsight.model_metadata as any)?.confidence ?? 0.65)}
          timestamp={latestInsight.created_at}
        />
      ) : null}
    </div>
  );
}

function formatMinutes(value: number | null | undefined) {
  if (!value) return '—';
  return (value / 60).toFixed(1);
}

function diffString(value?: number | null, baseline?: number | null) {
  if (!value || !baseline) return '—';
  const diff = value - baseline;
  const sign = diff >= 0 ? '+' : '−';
  return `${sign}${Math.abs(diff).toFixed(0)}`;
}

function determineStatus(value?: number | null, inverse = false) {
  if (value === null || value === undefined) return 'neutral';
  if (inverse) {
    if (value <= 50) return 'positive';
    if (value >= 70) return 'negative';
    return 'neutral';
  }
  if (value >= 80) return 'positive';
  if (value <= 50) return 'negative';
  return 'neutral';
}
