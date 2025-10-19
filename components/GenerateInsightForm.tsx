'use client';

import { useState, useTransition } from 'react';

import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { generateInsights } from '@/lib/llm/client';

const topics = [
  { value: 'daily', label: 'Daily briefing' },
  { value: 'weekly', label: 'Weekly review' },
  { value: 'nutrition', label: 'Nutrition coaching' },
  { value: 'training', label: 'Race-training focus' }
] as const;

interface GenerateInsightFormProps {
  userId: string;
  disabled?: boolean;
  disabledReason?: string | null;
}

export function GenerateInsightForm({ userId, disabled = false, disabledReason }: GenerateInsightFormProps) {
  const [topic, setTopic] = useState<typeof topics[number]['value']>('daily');
  const [isPending, startTransition] = useTransition();

  async function handleGenerate() {
    if (disabled) return;

    const today = new Date();
    const to = today.toISOString().slice(0, 10);
    const from = new Date(today.getTime() - 7 * 86400000).toISOString().slice(0, 10);

    startTransition(async () => {
      try {
        await generateInsights({ userId, from, to, topics: [topic] });
        toast({ title: 'Insights requested', description: 'Refresh to view the latest coaching tips.' });
      } catch (error) {
        console.error(error);
        toast({ title: 'Unable to generate insights', variant: 'destructive' });
      }
    });
  }

  return (
    <div className="flex items-center gap-3">
      <label className="text-sm">
        <span className="mr-2 font-medium">Topic</span>
        <select
          value={topic}
          onChange={(event) => setTopic(event.target.value as typeof topic)}
          className="rounded-md border border-border bg-background px-2 py-1 text-sm"
        >
          {topics.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <Button onClick={handleGenerate} disabled={disabled || isPending}>
        {isPending ? 'Generating…' : 'Generate insight'}
      </Button>
      {disabledReason ? <p className="text-xs text-muted-foreground">{disabledReason}</p> : null}
    </div>
  );
}
