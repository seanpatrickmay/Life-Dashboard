import { useMemo, useCallback } from 'react';
import styled from 'styled-components';
import { format, parseISO, isSameDay, addDays } from 'date-fns';

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

    const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const sortedEvents = [...eventsQuery.data.events]
      .filter(event => event.start_time && event.summary)
      .filter(event => {
        if (!event.end_time) return true;
        return new Date(event.end_time).getTime() > startOfToday.getTime();
      })
      .sort((a, b) => {
        const timeA = new Date(a.start_time!).getTime();
        const timeB = new Date(b.start_time!).getTime();
        return timeA - timeB;
      });

    const grouped: Array<{ date: Date; events: typeof sortedEvents }> = [];
    let currentDate: Date | null = null;
    let currentGroup: typeof sortedEvents = [];

    sortedEvents.forEach(event => {
      const eventDate = parseISO(event.start_time!);

      if (!currentDate || !isSameDay(currentDate, eventDate)) {
        if (currentGroup.length > 0) {
          grouped.push({ date: currentDate!, events: currentGroup });
        }
        currentDate = eventDate;
        currentGroup = [event];
      } else {
        currentGroup.push(event);
      }
    });

    if (currentGroup.length > 0 && currentDate) {
      grouped.push({ date: currentDate, events: currentGroup });
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

  const formatDateHeader = useCallback((date: Date) => {
    if (isSameDay(date, today)) return 'Today';
    if (isSameDay(date, addDays(today, 1))) return 'Tomorrow';
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
          {groupedEvents.map(({ date, events }) => (
            <div key={date.toISOString()}>
              <DateDivider data-halo="body">
                {formatDateHeader(date)}
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
