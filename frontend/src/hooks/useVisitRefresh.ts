import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { triggerVisitRefresh, type RefreshStatusResponse } from '../services/api';
import { isGuestMode } from '../demo/guest/guestMode';

const MIN_POLL_DELAY_MS = 1000 * 60 * 30;
const IN_PROGRESS_POLL_MS = 1000 * 30;
const ERROR_POLL_MS = 1000 * 60 * 60;
const HIDDEN_POLL_MS = 1000 * 60 * 60 * 2;

export function useVisitRefresh() {
  const queryClient = useQueryClient();
  const timerRef = useRef<number | null>(null);
  const lastCompletionRef = useRef<string | null>(null);

  useEffect(() => {
    if (isGuestMode()) return;
    let cancelled = false;
    const isVisible = () => document.visibilityState !== 'hidden';

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
          delay = Math.max(msUntil, 0);
        } else {
          delay = status.cooldown_seconds * 1000;
        }
      }
      if (!status?.running) {
        delay = Math.max(delay, MIN_POLL_DELAY_MS);
      }
      if (!isVisible()) {
        delay = Math.max(delay, HIDDEN_POLL_MS);
      }
      clearTimer();
      timerRef.current = window.setTimeout(ping, delay);
    };

    const invalidateDataCaches = () => {
      void queryClient.invalidateQueries({ queryKey: ['metrics-overview'] });
      void queryClient.invalidateQueries({ queryKey: ['readiness-summary'] });
      void queryClient.invalidateQueries({ queryKey: ['insight'] });
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

    const handleVisibilityChange = () => {
      if (cancelled) return;
      if (isVisible()) {
        clearTimer();
        void ping();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    ping();

    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      clearTimer();
    };
  }, [queryClient]);
}
