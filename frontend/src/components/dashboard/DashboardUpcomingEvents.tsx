import { useMemo, useCallback } from 'react';
import styled from 'styled-components';
import { format, parseISO, addDays } from 'date-fns';

import { Card } from '../common/Card';
import { useCalendarEvents } from '../../hooks/useCalendar';

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
`;

const Heading = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.85rem, 1.8vw, 0.95rem);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  flex-shrink: 0;
`;

const EventsList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  max-height: 380px;

  &::-webkit-scrollbar { width: 3px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 2px;
  }
`;

const EventRow = styled.div`
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 4px;
  border-radius: 10px;
  transition: background 0.15s ease;

  &:hover {
    background: ${({ theme }) => theme.colors.overlayHover};
  }
`;

const EventTime = styled.span`
  flex-shrink: 0;
  width: 6.5em;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.6;
  text-align: left;
`;

const EventDetails = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
`;

const EventSummary = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.88rem;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const EventLocation = styled.span`
  font-size: 0.7rem;
  opacity: 0.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const EmptyState = styled.p`
  margin: 0;
  font-size: 0.82rem;
  opacity: 0.6;
  text-align: center;
  padding: 12px 0;
`;

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  font-size: 0.9rem;
  opacity: 0.5;
`;

const DateDivider = styled.div`
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.45;
  margin-top: 6px;
  padding: 0 4px 3px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderSubtle};

  &:first-child {
    margin-top: 0;
  }
`;

export function DashboardUpcomingEvents() {
  const today = new Date();
  const startDate = today.toISOString().split('T')[0];
  const endDate = addDays(today, 7).toISOString().split('T')[0];

  const { eventsQuery } = useCalendarEvents(startDate, endDate);

  const groupedEvents = useMemo(() => {
    if (!eventsQuery.data?.events) return [];

    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    const endStr = addDays(today, 7).toISOString().split('T')[0];

    // getLocalDateStr returns YYYY-MM-DD for placing an event into a date bucket:
    // - all-day events: use the UTC date of start_time (canonical date per backend)
    // - timed events: use local date of start_time
    const getLocalDateStr = (event: typeof eventsQuery.data.events[0]): string => {
      if (!event.start_time) return '';
      if (event.is_all_day) {
        return new Date(event.start_time).toISOString().slice(0, 10);
      }
      const d = new Date(event.start_time);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };

    const sortedEvents = [...eventsQuery.data.events]
      .filter(event => event.summary)
      .filter(event => {
        if (!event.start_time) return false;
        const dateStr = getLocalDateStr(event);
        if (!dateStr) return false;
        // For all-day events with exclusive end, also check end_time
        if (event.is_all_day && event.end_time) {
          const endDateStr = new Date(event.end_time).toISOString().slice(0, 10);
          // Exclude if end is on or before today (event fully in the past)
          if (endDateStr <= todayStr) return false;
        }
        return dateStr <= endStr;
      })
      .sort((a, b) => {
        const strA = getLocalDateStr(a);
        const strB = getLocalDateStr(b);
        if (strA !== strB) return strA < strB ? -1 : 1;
        // Within the same day, all-day events sort first
        if (a.is_all_day && !b.is_all_day) return -1;
        if (!a.is_all_day && b.is_all_day) return 1;
        return new Date(a.start_time!).getTime() - new Date(b.start_time!).getTime();
      });

    const grouped: Array<{ dateStr: string; date: Date; events: typeof sortedEvents }> = [];
    let currentDateStr = '';
    let currentGroup: typeof sortedEvents = [];

    sortedEvents.forEach(event => {
      const eventDateStr = getLocalDateStr(event);

      if (eventDateStr !== currentDateStr) {
        if (currentGroup.length > 0) {
          // Build a local noon Date for the previous date string to avoid
          // midnight boundary issues in formatDateHeader comparisons.
          const [y, mo, d] = currentDateStr.split('-').map(Number);
          grouped.push({ dateStr: currentDateStr, date: new Date(y, mo - 1, d, 12, 0, 0), events: currentGroup });
        }
        currentDateStr = eventDateStr;
        currentGroup = [event];
      } else {
        currentGroup.push(event);
      }
    });

    if (currentGroup.length > 0 && currentDateStr) {
      const [y, mo, d] = currentDateStr.split('-').map(Number);
      grouped.push({ dateStr: currentDateStr, date: new Date(y, mo - 1, d, 12, 0, 0), events: currentGroup });
    }

    return grouped;
  }, [eventsQuery.data]);

  const formatEventTime = useCallback((startTime: string | null, endTime: string | null, isAllDay: boolean) => {
    if (isAllDay) return 'All day';
    if (!startTime) return '';

    const start = parseISO(startTime);
    const startFormatted = format(start, 'h:mm a');

    if (!endTime) return startFormatted;

    const end = parseISO(endTime);
    return `${startFormatted}–${format(end, 'h:mm a')}`;
  }, []);

  const formatDateHeader = useCallback((date: Date, dateStr: string) => {
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    const tmrw = addDays(today, 1);
    const tomorrowStr = `${tmrw.getFullYear()}-${String(tmrw.getMonth() + 1).padStart(2, '0')}-${String(tmrw.getDate()).padStart(2, '0')}`;
    if (dateStr === todayStr) return 'Today';
    if (dateStr === tomorrowStr) return 'Tomorrow';
    return format(date, 'EEE, MMM d');
  }, [today]);

  return (
    <Panel>
      <Heading data-halo="heading">Upcoming</Heading>

      {eventsQuery.isLoading ? (
        <LoadingState>Loading...</LoadingState>
      ) : groupedEvents.length === 0 ? (
        <EmptyState>No events in the next 7 days</EmptyState>
      ) : (
        <EventsList>
          {groupedEvents.map(({ dateStr, date, events }) => (
            <div key={dateStr}>
              <DateDivider data-halo="body">
                {formatDateHeader(date, dateStr)}
              </DateDivider>
              {events.map(event => (
                <EventRow key={event.id}>
                  <EventTime data-halo="body">
                    {formatEventTime(event.start_time, event.end_time, event.is_all_day)}
                  </EventTime>
                  <EventDetails>
                    <EventSummary data-halo="body">
                      {event.summary}
                    </EventSummary>
                    {event.location && (
                      <EventLocation data-halo="body">
                        {event.location}
                      </EventLocation>
                    )}
                  </EventDetails>
                </EventRow>
              ))}
            </div>
          ))}
        </EventsList>
      )}
    </Panel>
  );
}
