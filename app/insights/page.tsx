import { redirect } from 'next/navigation';

import { GenerateInsightForm } from '@/components/GenerateInsightForm';
import { LLMInsightCard } from '@/components/LLMInsightCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { isSubscriptionActive } from '@/lib/billing';
import { getCurrentUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';

const FREE_INSIGHTS_PER_MONTH = Number(process.env.NEXT_PUBLIC_FREE_INSIGHTS_LIMIT ?? 5);

export default async function InsightsPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login');
  }

  const supabase = getSupabaseServerClient();
  const now = new Date();
  const startOfMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));

  const [insightsResult, subscriptionResult, usageResult] = await Promise.all([
    supabase
      .from('insights')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })
      .limit(20),
    supabase.from('subscriptions').select('status,current_period_end').eq('user_id', user.id).maybeSingle(),
    supabase
      .from('insights')
      .select('id', { count: 'exact', head: true })
      .eq('user_id', user.id)
      .gte('created_at', startOfMonth.toISOString())
  ]);

  if (insightsResult.error) throw insightsResult.error;
  if (subscriptionResult.error) throw subscriptionResult.error;
  if (usageResult.error) throw usageResult.error;

  const insights = insightsResult.data ?? [];
  const monthlyUsage = usageResult.count ?? 0;
  const remainingFreeInsights = Math.max(FREE_INSIGHTS_PER_MONTH - monthlyUsage, 0);
  const subscription = subscriptionResult.data ?? null;
  const isPremium = isSubscriptionActive(subscription, now);
  const canGenerateInsight = isPremium || remainingFreeInsights > 0;
  const disabledReason = canGenerateInsight
    ? null
    : 'You have used all free insights this month. Upgrade to continue.';

  return (
    <div className="space-y-6 py-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Insights</h1>
          {!isPremium ? (
            <p className="text-sm text-muted-foreground">
              {remainingFreeInsights > 0
                ? `You have ${remainingFreeInsights} free insight${remainingFreeInsights === 1 ? '' : 's'} remaining this month.`
                : 'Upgrade to Pro for unlimited insights.'}
            </p>
          ) : null}
        </div>
        <GenerateInsightForm userId={user.id} disabled={!canGenerateInsight} disabledReason={disabledReason} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {insights.map((insight) => {
            const metadata = (insight.model_metadata ?? {}) as Record<string, unknown>;
            const bullets = (metadata['bullets'] ?? []) as string[];
            const actions = (insight.actions ?? []) as string[];
            const confidence = Number(metadata['confidence'] ?? 0.6);

            return (
              <LLMInsightCard
                key={insight.id}
                title={insight.topic}
                summary={insight.summary}
                bullets={bullets}
                actions={actions}
                confidence={confidence}
                timestamp={insight.created_at}
              />
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
