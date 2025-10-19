import { redirect } from 'next/navigation';

import { ConnectionManager } from '@/components/ConnectionManager';
import { SettingsPaywall } from '@/components/SettingsPaywall';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getCurrentUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';
import { resolveConnectionStatus as resolveGarminStatus } from '@/lib/providers/garmin';
import { resolveWithingsStatus } from '@/lib/providers/withings';
import { PortalButton } from '@/components/PortalButton';

export default async function SettingsPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login');
  }

  const supabase = getSupabaseServerClient();

  const [{ data: profile }, { data: connections }, { data: subscription }] = await Promise.all([
    supabase.from('profiles').select('*').eq('id', user.id).maybeSingle(),
    supabase.from('connections').select('*').eq('user_id', user.id),
    supabase.from('subscriptions').select('*').eq('user_id', user.id).maybeSingle()
  ]);

  const garmin = connections?.find((c) => c.provider === 'garmin');
  const withings = connections?.find((c) => c.provider === 'withings');
  const garminStatus = resolveGarminStatus(garmin?.latest_sync_at, garmin?.status);
  const withingsStatus = resolveWithingsStatus(withings?.latest_sync_at, withings?.status);

  return (
    <div className="space-y-6 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>Baseline data for calculations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span>Email</span>
              <span className="font-medium">{profile?.email ?? user.email}</span>
            </div>
            <div className="flex justify-between">
              <span>Unit system</span>
              <span className="font-medium capitalize">{profile?.default_unit_system ?? 'metric'}</span>
            </div>
            <Button variant="outline" className="mt-4" formAction="#">
              Edit profile
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Device connections</CardTitle>
            <CardDescription>Link providers to enable automatic sync</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Garmin</p>
                <p className="text-xs text-muted-foreground">Activities, sleep, heart rate, stress</p>
              </div>
              <ConnectionManager
                provider="garmin"
                status={garminStatus}
                authUrl="/api/oauth/garmin"
                latestSyncAt={garmin?.latest_sync_at}
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Withings</p>
                <p className="text-xs text-muted-foreground">Body metrics from smart scale</p>
              </div>
              <ConnectionManager
                provider="withings"
                status={withingsStatus}
                authUrl="/api/oauth/withings"
                latestSyncAt={withings?.latest_sync_at}
              />
            </div>
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Billing</CardTitle>
            <CardDescription>Manage your subscription</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground">Status</p>
              <p className="text-lg font-semibold">{subscription?.status ?? 'trialing'}</p>
            </div>
            <PortalButton />
          </CardContent>
        </Card>
        <SettingsPaywall />
      </div>
    </div>
  );
}
