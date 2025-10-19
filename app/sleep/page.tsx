import { redirect } from 'next/navigation';

import { TrendLine } from '@/components/TrendLine';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getCurrentUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';

export default async function SleepPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login');
  }

  const supabase = getSupabaseServerClient();
  const { data } = await supabase
    .from('daily_metrics')
    .select('metric_date, sleep_minutes_total, sleep_efficiency, hrv_rmssd')
    .eq('user_id', user.id)
    .order('metric_date', { ascending: true })
    .limit(30);

  const sleepMinutes = (data ?? []).map((row) => Number(row.sleep_minutes_total ?? 0) / 60);
  const efficiency = (data ?? []).map((row) => Number(row.sleep_efficiency ?? 0));
  const hrv = (data ?? []).map((row) => Number(row.hrv_rmssd ?? 0));

  return (
    <div className="space-y-6 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Sleep & Recovery</h1>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Sleep duration (hrs)</CardTitle>
          </CardHeader>
          <CardContent>
            <TrendLine values={sleepMinutes} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Sleep efficiency (%)</CardTitle>
          </CardHeader>
          <CardContent>
            <TrendLine values={efficiency} stroke="hsl(var(--primary))" />
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>HRV (rMSSD)</CardTitle>
        </CardHeader>
        <CardContent>
          <TrendLine values={hrv} stroke="hsl(var(--secondary))" />
        </CardContent>
      </Card>
    </div>
  );
}
