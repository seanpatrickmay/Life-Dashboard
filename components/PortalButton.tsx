'use client';

import { useTransition } from 'react';

import { createPortalSession } from '@/lib/stripe';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';

export function PortalButton() {
  const [isPending, startTransition] = useTransition();

  function handleClick() {
    startTransition(async () => {
      try {
        const url = await createPortalSession();
        window.location.href = url;
      } catch (error) {
        console.error(error);
        toast({ title: 'Unable to open billing portal', variant: 'destructive' });
      }
    });
  }

  return (
    <Button type="button" onClick={handleClick} disabled={isPending}>
      {isPending ? 'Opening…' : 'Open customer portal'}
    </Button>
  );
}
