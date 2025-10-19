'use client';

import { useTransition } from 'react';

import { createCheckoutSession } from '@/lib/stripe';
import { Paywall } from '@/components/Paywall';
import { toast } from '@/components/ui/use-toast';

interface SettingsPaywallProps {
  plan?: 'monthly' | 'yearly';
}

export function SettingsPaywall({ plan = 'monthly' }: SettingsPaywallProps) {
  const [isPending, startTransition] = useTransition();

  async function handleUpgrade() {
    startTransition(async () => {
      try {
        const url = await createCheckoutSession({
          plan,
          successUrl: `${window.location.origin}/settings`,
          cancelUrl: `${window.location.origin}/settings`
        });
        window.location.href = url;
      } catch (error) {
        console.error(error);
        toast({ title: 'Unable to start checkout', variant: 'destructive' });
      }
    });
  }

  return <Paywall onUpgrade={handleUpgrade} disabled={isPending} />;
}
