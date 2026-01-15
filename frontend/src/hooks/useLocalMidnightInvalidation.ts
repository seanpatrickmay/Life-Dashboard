import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const DAY_SCOPED_KEYS: Array<readonly unknown[]> = [
  ['todos'],
  ['journal'],
  ['insight'],
  ['readiness-summary'],
  ['metrics-overview'],
  ['nutrition', 'summary'],
  ['nutrition', 'history'],
  ['nutrition', 'menu']
];

export function useLocalMidnightInvalidation() {
  const queryClient = useQueryClient();
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    const scheduleNext = () => {
      const now = new Date();
      const nextMidnight = new Date(now);
      nextMidnight.setHours(24, 0, 0, 0);
      const delay = nextMidnight.getTime() - now.getTime();
      timerRef.current = window.setTimeout(() => {
        DAY_SCOPED_KEYS.forEach((key) => {
          void queryClient.invalidateQueries({ queryKey: key });
        });
        scheduleNext();
      }, delay);
    };

    scheduleNext();

    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, [queryClient]);
}
