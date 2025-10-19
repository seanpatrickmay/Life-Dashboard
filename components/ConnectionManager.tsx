'use client';

import { useState } from 'react';

import { ConnectionButton } from '@/components/ConnectionButton';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';

interface ConnectionManagerProps {
  provider: 'garmin' | 'withings';
  status: 'connected' | 'paused' | 'revoked' | 'disconnected' | 'error';
  authUrl: string;
  latestSyncAt?: string | null;
  defaultDays?: number;
}

export function ConnectionManager({ provider, status, authUrl, latestSyncAt, defaultDays = 30 }: ConnectionManagerProps) {
  const [isResyncing, setResyncing] = useState(false);

  async function handleConnect() {
    window.location.href = authUrl;
  }

  async function handleDisconnect() {
    await fetch(`/api/settings/connections`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ provider })
    });
  }

  async function handleResync() {
    setResyncing(true);
    try {
      const response = await fetch('/api/settings/connections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, action: 'resync', days: defaultDays })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      toast({ title: 'Backfill requested' });
    } catch (error) {
      console.error(error);
      toast({ title: 'Unable to queue backfill', variant: 'destructive' });
    } finally {
      setResyncing(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-2 text-xs">
      <ConnectionButton provider={provider} status={status} onConnect={handleConnect} onDisconnect={handleDisconnect} />
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={handleResync} disabled={isResyncing}>
          {isResyncing ? 'Resyncing…' : 'Force backfill'}
        </Button>
        <span className="text-muted-foreground">
          Last sync: {latestSyncAt ? new Date(latestSyncAt).toLocaleString() : 'never'}
        </span>
      </div>
    </div>
  );
}
