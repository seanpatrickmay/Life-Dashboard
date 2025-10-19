'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/button';

const steps = [
  {
    title: 'Set your baseline',
    description: 'Add your profile details and preferred units so calculations are accurate.'
  },
  {
    title: 'Connect your devices',
    description: 'Link Garmin and Withings to sync workouts, sleep, and body metrics automatically.'
  },
  {
    title: 'Define nutrition goals',
    description: 'Set calorie and macro targets or import from your current plan.'
  }
];

interface OnboardingWizardProps {
  onComplete(): Promise<void>;
}

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [index, setIndex] = useState(0);
  const isLast = index === steps.length - 1;

  async function handleNext() {
    if (isLast) {
      await onComplete();
      return;
    }
    setIndex((prev) => prev + 1);
  }

  function handleBack() {
    setIndex((prev) => Math.max(0, prev - 1));
  }

  const step = steps[index];

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-dashed border-border bg-card p-6">
      <div className="flex items-center justify-between text-sm uppercase tracking-wide text-muted-foreground">
        <span>Step {index + 1}</span>
        <span>{steps.length} total</span>
      </div>
      <div>
        <h3 className="text-xl font-semibold">{step.title}</h3>
        <p className="mt-2 text-sm text-muted-foreground">{step.description}</p>
      </div>
      <div className="flex justify-between">
        <Button variant="ghost" onClick={handleBack} disabled={index === 0}>
          Back
        </Button>
        <Button onClick={handleNext}>{isLast ? 'Finish' : 'Next'}</Button>
      </div>
    </div>
  );
}
