import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { triggerVisitRefresh, type RefreshStatusResponse } from '../services/api';

const MIN_POLL_DELAY_MS = 5_000;
const IN_PROGRESS_POLL_MS = 10_000;
const ERROR_POLL_MS = 60_000;

export function useVisitRefresh() {
  const queryClient = useQueryClient();
  const timerRef = useRef<number | null>(null);
  const lastCompletionRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const clearTimer = () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    const scheduleNext = (status?: RefreshStatusResponse) => {
      if (cancelled) return;
      let delay = ERROR_POLL_MS;
      if (status) {
        if (status.running) {
          delay = IN_PROGRESS_POLL_MS;
        } else if (status.next_allowed_at) {
          const msUntil = new Date(status.next_allowed_at).getTime() - Date.now();
          delay = Math.max(msUntil, MIN_POLL_DELAY_MS);
        } else {
          delay = Math.max(status.cooldown_seconds * 1000, MIN_POLL_DELAY_MS);
        }
      }
      clearTimer();
      timerRef.current = window.setTimeout(ping, delay);
    };

    const invalidateDataCaches = () => {
      void queryClient.invalidateQueries({ queryKey: ['metrics-overview'] });
      void queryClient.invalidateQueries({ queryKey: ['readiness-summary'] });
      void queryClient.invalidateQueries({ queryKey: ['insight'] });
      void queryClient.invalidateQueries({ queryKey: ['user', 'profile'] });
      void queryClient.invalidateQueries({ queryKey: ['nutrition', 'goals'] });
      void queryClient.invalidateQueries({ queryKey: ['nutrition', 'summary'] });
      void queryClient.invalidateQueries({ queryKey: ['nutrition', 'history'] });
    };

    const handleStatus = (status: RefreshStatusResponse) => {
      const completedAt = status.last_completed_at ?? null;
      if (completedAt && completedAt !== lastCompletionRef.current) {
        lastCompletionRef.current = completedAt;
        invalidateDataCaches();
      }
    };

    const ping = async () => {
      try {
        const status = await triggerVisitRefresh();
        if (cancelled) return;
        handleStatus(status);
        scheduleNext(status);
      } catch (error) {
        if (!cancelled) {
          scheduleNext();
        }
      }
    };

    ping();

    return () => {
      cancelled = true;
      clearTimer();
    };
  }, [queryClient]);
}
