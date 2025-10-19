import { redirect } from 'next/navigation';

import { GoalEditorSection } from '@/components/GoalEditorSection';
import { ProgressRing } from '@/components/ProgressRing';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { NutritionEntryForm } from '@/components/NutritionEntryForm';
import { getCurrentUser } from '@/lib/auth';
import { getSupabaseServerClient } from '@/lib/supabase';

interface NutritionPageProps {
  searchParams?: {
    date?: string;
  };
}

const macroKeys = [
  { actualKey: 'calories', targetKey: 'energy_kcal_target', label: 'Calories', unit: 'kcal' },
  { actualKey: 'protein_g', targetKey: 'protein_g_target', label: 'Protein', unit: 'g' },
  { actualKey: 'carbs_g', targetKey: 'carbs_g_target', label: 'Carbs', unit: 'g' },
  { actualKey: 'fat_g', targetKey: 'fat_g_target', label: 'Fat', unit: 'g' },
  { actualKey: 'fiber_g', targetKey: 'fiber_g_target', label: 'Fiber', unit: 'g' }
] as const;

export default async function NutritionPage({ searchParams }: NutritionPageProps) {
  const user = await getCurrentUser();
  if (!user) {
    redirect('/login');
  }

  const date = searchParams?.date ?? new Date().toISOString().slice(0, 10);
  const supabase = getSupabaseServerClient();

  const [{ data: entries }, { data: macro }, { data: goals }] = await Promise.all([
    supabase
      .from('nutrition_entries')
      .select('*')
      .eq('user_id', user.id)
      .gte('entry_timestamp', new Date(date).toISOString())
      .lt('entry_timestamp', new Date(new Date(date).getTime() + 86400000).toISOString())
      .order('entry_timestamp', { ascending: true }),
    supabase
      .from('v_macro_compliance')
      .select('*')
      .eq('user_id', user.id)
      .eq('entry_date', date)
      .maybeSingle(),
    supabase
      .from('nutrition_goals')
      .select('*')
      .eq('user_id', user.id)
      .order('updated_at', { ascending: false })
      .limit(1)
      .maybeSingle()
  ]);

  const macroData = macro ?? {};
  const goalData = goals ?? {};

  return (
    <div className="space-y-6 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Nutrition</h1>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Daily intake</CardTitle>
            <CardDescription>{new Date(date).toLocaleDateString()}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              {macroKeys.map(({ actualKey, targetKey, label, unit }) => {
                const actual = Number(macroData[actualKey] ?? 0);
                const target = Number(macroData[targetKey] ?? goalData[targetKey]);
                return (
                  <div key={actualKey} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{label}</span>
                      <span className="text-muted-foreground">
                        {actual}
                        {unit}
                        {target ? ` / ${target}${unit}` : ''}
                      </span>
                    </div>
                    <Progress value={actual} max={target || actual || 1} />
                  </div>
                );
              })}
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase text-muted-foreground">Entries</h3>
              <NutritionEntryForm date={date} />
              <div className="h-px w-full bg-border" />
              <ul className="space-y-3 text-sm">
                {(entries ?? []).map((entry) => (
                  <li key={entry.id} className="flex items-center justify-between rounded-md border border-border p-3">
                    <div>
                      <p className="font-medium">{entry.food_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(entry.entry_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ·{' '}
                        {entry.calories ?? 0} kcal
                      </p>
                    </div>
                    <div className="space-x-2 text-xs text-muted-foreground">
                      <span>P {entry.protein_g ?? 0}g</span>
                      <span>C {entry.carbs_g ?? 0}g</span>
                      <span>F {entry.fat_g ?? 0}g</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Goal progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-center">
              <ProgressRing value={Number((macroData.calories_ratio ?? 0) * 100)} max={150} label="Calories" />
            </div>
            <GoalEditorSection
              defaultGoals={{
                calories: goalData.energy_kcal_target,
                protein: goalData.protein_g_target,
                carbs: goalData.carbs_g_target,
                fat: goalData.fat_g_target,
                fiber: goalData.fiber_g_target
              }}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
