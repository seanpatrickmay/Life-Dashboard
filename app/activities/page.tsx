import { redirect } from 'next/navigation';

import { TrendLine } from '@/components/TrendLine';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { getCurrentUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';

export default async function ActivitiesPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login');
  }

  const supabase = getSupabaseServerClient();
  const [{ data: activities }, { data: loadBalance }] = await Promise.all([
    supabase
      .from('activities')
      .select('id, name, sport_type, start_time, duration_s, distance_m, tss_est, trimp')
      .eq('user_id', user.id)
      .order('start_time', { ascending: false })
      .limit(25),
    supabase
      .from('v_training_load_balance')
      .select('metric_date, training_load, atl, ctl, tsb')
      .eq('user_id', user.id)
      .order('metric_date', { ascending: true })
  ]);

  const ctlSeries = (loadBalance ?? []).map((row) => Number(row.ctl ?? 0));
  const atlSeries = (loadBalance ?? []).map((row) => Number(row.atl ?? 0));

  return (
    <div className="space-y-6 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Activities</h1>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Training load balance</CardTitle>
            <CardDescription>CTL vs ATL</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="text-xs uppercase text-muted-foreground">Chronic load</h4>
              <TrendLine values={ctlSeries} />
            </div>
            <div>
              <h4 className="text-xs uppercase text-muted-foreground">Acute load</h4>
              <TrendLine values={atlSeries} stroke="hsl(var(--destructive))" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent sessions</CardTitle>
            <CardDescription>Last 25 workouts</CardDescription>
          </CardHeader>
          <CardContent>
            <table className="w-full table-fixed text-sm">
              <thead className="text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-32">Date</th>
                  <th>Session</th>
                  <th className="w-16">Dur.</th>
                  <th className="w-16">Dist.</th>
                  <th className="w-16">TSS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(activities ?? []).map((activity) => (
                  <tr key={activity.id} className="whitespace-nowrap">
                    <td>{new Date(activity.start_time).toLocaleDateString()}</td>
                    <td>
                      <div className="font-medium">{activity.name ?? activity.sport_type}</div>
                      <div className="text-xs text-muted-foreground">{activity.sport_type}</div>
                    </td>
                    <td>{formatMinutes(activity.duration_s)}</td>
                    <td>{activity.distance_m ? (activity.distance_m / 1000).toFixed(1) : '—'} km</td>
                    <td>{activity.tss_est ?? activity.trimp ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function formatMinutes(duration?: number | null) {
  if (!duration) return '—';
  const minutes = Math.round(duration / 60);
  return `${minutes}m`;
}
