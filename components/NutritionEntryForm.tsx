'use client';

import { useState, useTransition } from 'react';

import { createNutritionEntryAction } from '@/app/nutrition/actions';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';

export function NutritionEntryForm({ date }: { date: string }) {
  const [form, setForm] = useState({
    foodName: '',
    calories: '',
    protein: '',
    carbs: '',
    fat: ''
  });
  const [isPending, startTransition] = useTransition();

  function updateField(key: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function reset() {
    setForm({ foodName: '', calories: '', protein: '', carbs: '', fat: '' });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(async () => {
      try {
        await createNutritionEntryAction({
          timestamp: new Date(`${date}T12:00:00Z`),
          foodName: form.foodName,
          calories: Number(form.calories) || 0,
          protein_g: Number(form.protein) || 0,
          carbs_g: Number(form.carbs) || 0,
          fat_g: Number(form.fat) || 0
        });
        toast({ title: 'Entry added' });
        reset();
      } catch (error) {
        console.error(error);
        toast({ title: 'Unable to add entry', variant: 'destructive' });
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 rounded-md border border-border p-4 text-sm">
      <div className="grid gap-2">
        <label className="flex flex-col gap-1">
          <span className="font-medium">Food</span>
          <input
            required
            value={form.foodName}
            onChange={(event) => updateField('foodName', event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2"
            placeholder="Overnight oats"
          />
        </label>
        <div className="grid grid-cols-4 gap-2">
          {[
            { key: 'calories', label: 'kcal' },
            { key: 'protein', label: 'g protein' },
            { key: 'carbs', label: 'g carbs' },
            { key: 'fat', label: 'g fat' }
          ].map((field) => (
            <label key={field.key} className="flex flex-col gap-1">
              <span className="font-medium capitalize">{field.key}</span>
              <input
                type="number"
                min={0}
                className="rounded-md border border-border bg-background px-2 py-1"
                value={form[field.key as keyof typeof form]}
                onChange={(event) => updateField(field.key as keyof typeof form, event.target.value)}
              />
              <span className="text-xs text-muted-foreground">{field.label}</span>
            </label>
          ))}
        </div>
      </div>
      <Button type="submit" disabled={isPending}>
        {isPending ? 'Saving…' : 'Add entry'}
      </Button>
    </form>
  );
}
