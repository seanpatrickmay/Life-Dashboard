import { useState } from 'react';

import { Button } from '@/components/ui/button';

interface GoalEditorProps {
  defaultGoals: {
    calories?: number | null;
    protein?: number | null;
    carbs?: number | null;
    fat?: number | null;
    fiber?: number | null;
  };
  onSave(goals: GoalEditorProps['defaultGoals']): Promise<void>;
  disabled?: boolean;
}

export function GoalEditor({ defaultGoals, onSave, disabled }: GoalEditorProps) {
  const [goals, setGoals] = useState(defaultGoals);
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    try {
      await onSave(goals);
    } finally {
      setIsSaving(false);
    }
  }

  const isDisabled = disabled || isSaving;

  return (
    <form className="grid gap-4" onSubmit={handleSubmit}>
      <div className="grid grid-cols-2 gap-3">
        {(['calories', 'protein', 'carbs', 'fat', 'fiber'] as const).map((key) => (
          <label key={key} className="flex flex-col gap-1 text-sm">
            <span className="font-medium capitalize">{key}</span>
            <input
              type="number"
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={goals[key] ?? ''}
              min={0}
              disabled={isDisabled}
              onChange={(event) =>
                setGoals((prev) => ({
                  ...prev,
                  [key]: Number(event.target.value)
                }))
              }
            />
          </label>
        ))}
      </div>
      <Button type="submit" disabled={isDisabled}>
        {isSaving ? 'Saving...' : 'Save goals'}
      </Button>
    </form>
  );
}
