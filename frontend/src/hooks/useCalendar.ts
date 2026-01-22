import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchCalendarEvents,
  fetchCalendarStatus,
  fetchCalendars,
  syncCalendar,
  updateCalendarEvent,
  updateCalendarSelection,
  type CalendarEvent,
  type CalendarListResponse,
  type CalendarStatus
} from '../services/api';

const CALENDAR_STATUS_KEY = ['calendar', 'status'];
const CALENDAR_LIST_KEY = ['calendar', 'list'];
const CALENDAR_EVENTS_KEY = ['calendar', 'events'];

export function useCalendarStatus() {
  return useQuery<CalendarStatus>({
    queryKey: CALENDAR_STATUS_KEY,
    queryFn: fetchCalendarStatus
  });
}

export function useCalendars() {
  const queryClient = useQueryClient();
  const calendarsQuery = useQuery<CalendarListResponse>({
    queryKey: CALENDAR_LIST_KEY,
    queryFn: fetchCalendars
  });

  const updateSelection = useMutation({
    mutationFn: (googleIds: string[]) => updateCalendarSelection(googleIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CALENDAR_LIST_KEY });
    }
  });

  return {
    calendarsQuery,
    updateSelection: updateSelection.mutateAsync
  };
}

export function useCalendarEvents(start: string, end: string, enabled = true) {
  const queryClient = useQueryClient();
  const eventsQuery = useQuery({
    queryKey: [...CALENDAR_EVENTS_KEY, start, end],
    queryFn: () => fetchCalendarEvents(start, end),
    enabled: enabled && Boolean(start && end)
  });

  const syncMutation = useMutation({
    mutationFn: () => syncCalendar(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CALENDAR_EVENTS_KEY });
      queryClient.invalidateQueries({ queryKey: CALENDAR_LIST_KEY });
      queryClient.invalidateQueries({ queryKey: CALENDAR_STATUS_KEY });
    }
  });

  const updateEventMutation = useMutation({
    mutationFn: (payload: {
      id: number;
      summary?: string;
      start_time?: string;
      end_time?: string;
      scope?: string;
      is_all_day?: boolean;
    }) =>
      updateCalendarEvent(payload.id, {
        summary: payload.summary,
        start_time: payload.start_time,
        end_time: payload.end_time,
        scope: payload.scope,
        is_all_day: payload.is_all_day
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CALENDAR_EVENTS_KEY });
    }
  });

  return {
    eventsQuery,
    syncCalendar: syncMutation.mutateAsync,
    updateCalendarEvent: updateEventMutation.mutateAsync,
    isSyncing: syncMutation.isPending
  };
}

export type { CalendarEvent };
