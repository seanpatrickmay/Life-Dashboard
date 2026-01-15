import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { createJournalEntry, fetchJournalDay, fetchJournalWeek } from '../services/api';
import { getUserTimeZone } from '../utils/timeZone';

const JOURNAL_DAY_KEY = ['journal', 'day'];
const JOURNAL_WEEK_KEY = ['journal', 'week'];

export function useJournal(selectedDate: string, weekStart: string) {
  const queryClient = useQueryClient();
  const timeZone = useMemo(() => getUserTimeZone(), []);

  const dayQuery = useQuery({
    queryKey: [...JOURNAL_DAY_KEY, selectedDate, timeZone],
    queryFn: () => fetchJournalDay(selectedDate, timeZone)
  });

  const weekQuery = useQuery({
    queryKey: [...JOURNAL_WEEK_KEY, weekStart, timeZone],
    queryFn: () => fetchJournalWeek(weekStart, timeZone)
  });

  const createMutation = useMutation({
    mutationFn: (text: string) => createJournalEntry({ text, time_zone: timeZone }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOURNAL_DAY_KEY });
      queryClient.invalidateQueries({ queryKey: JOURNAL_WEEK_KEY });
    }
  });

  return {
    timeZone,
    dayQuery,
    weekQuery,
    createEntry: createMutation.mutateAsync,
    isSavingEntry: createMutation.isPending
  };
}
