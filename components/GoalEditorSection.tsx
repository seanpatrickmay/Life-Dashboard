'use client';

import { useTransition } from 'react';

import { GoalEditor } from '@/components/GoalEditor';
import { updateNutritionGoalsAction } from '@/app/nutrition/actions';
import { toast } from '@/components/ui/use-toast';

interface GoalEditorSectionProps {
  defaultGoals: {
    calories?: number | null;
    protein?: number | null;
    carbs?: number | null;
    fat?: number | null;
    fiber?: number | null;
  };
}

export function GoalEditorSection({ defaultGoals }: GoalEditorSectionProps) {
  const [isPending, startTransition] = useTransition();

  async function handleSave(goals: GoalEditorSectionProps['defaultGoals']) {
    startTransition(async () => {
      try {
        await updateNutritionGoalsAction({
          calories: goals.calories ?? undefined,
          protein: goals.protein ?? undefined,
          carbs: goals.carbs ?? undefined,
          fat: goals.fat ?? undefined,
          fiber: goals.fiber ?? undefined
        });
        toast({ title: 'Goals updated' });
      } catch (error) {
        console.error(error);
        toast({ title: 'Unable to update goals', variant: 'destructive' });
      }
    });
  }

  return <GoalEditor defaultGoals={defaultGoals} onSave={handleSave} disabled={isPending} />;
}
