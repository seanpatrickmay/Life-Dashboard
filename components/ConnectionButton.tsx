import { useState } from 'react';

import { Button } from '@/components/ui/button';

interface ConnectionButtonProps {
  provider: 'garmin' | 'withings';
  status: 'connected' | 'paused' | 'revoked' | 'disconnected' | 'error';
  onConnect(): Promise<void>;
  onDisconnect(): Promise<void>;
}

export function ConnectionButton({ provider, status, onConnect, onDisconnect }: ConnectionButtonProps) {
  const [isLoading, setLoading] = useState(false);
  const isConnected = status === 'connected';

  async function handleClick() {
    setLoading(true);
    try {
      if (isConnected) {
        await onDisconnect();
      } else {
        await onConnect();
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button onClick={handleClick} variant={isConnected ? 'outline' : 'default'} disabled={isLoading}>
      {isLoading ? 'Please wait…' : isConnected ? `Disconnect ${provider}` : `Connect ${provider}`}
    </Button>
  );
}
