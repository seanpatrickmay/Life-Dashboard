import { useMemo, useCallback } from 'react';
import styled from 'styled-components';
import { format, parseISO, isSameDay, addDays } from 'date-fns';

import { Card } from '../common/Card';
import { useCalendarEvents } from '../../hooks/useCalendar';

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 2vw, 18px);
  overflow: hidden;
`;

const Heading = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.95rem, 2vw, 1.1rem);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  flex-shrink: 0;
`;

const EventsList = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(10px, 1.5vw, 14px);
  overflow-y: auto;
  max-height: 420px;

  /* Subtle scrollbar styling */
  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 2px;

    &:hover {
      background: ${({ theme }) => theme.colors.scrollThumb};
    }
  }
`;

const EventCard = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: clamp(10px, 2vw, 14px);
  border-radius: 18px;
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  transition: all 0.2s ease;

  &:hover {
    background: ${({ theme }) => theme.colors.overlayHover};
    border-color: ${({ theme }) => theme.colors.borderSubtle};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const EventTime = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.8;
`;

const EventSummary = styled.div`
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 1rem;
  line-height: 1.4;
`;

const EventLocation = styled.div`
  font-size: 0.85rem;
  opacity: 0.7;
  font-style: italic;
`;

const EmptyState = styled.p`
  margin: 0;
  font-size: 0.9rem;
  opacity: 0.8;
  text-align: center;
  padding: 20px;
`;

const LoadingState = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  font-size: 1.2rem;
  opacity: 0.6;
`;

const DateDivider = styled.div`
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.6;
  margin-top: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.borderSubtle};
`;

export function DashboardUpcomingEvents() {
  // Get events for the next 7 days
  const today = new Date();
  const startDate = today.toISOString().split('T')[0];
  const endDate = addDays(today, 7).toISOString().split('T')[0];

  const { eventsQuery } = useCalendarEvents(startDate, endDate);

  const groupedEvents = useMemo(() => {
    if (!eventsQuery.data?.events) return [];

    // Filter out events that ended at or before the start of today (e.g. yesterday's all-day events)
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

    // Group events by day
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
    const endFormatted = format(end, 'h:mm a');

    return `${startFormatted} - ${endFormatted}`;
  }, []);

  const formatDateHeader = useCallback((date: Date) => {
    if (isSameDay(date, today)) {
      return 'Today';
    }
    if (isSameDay(date, addDays(today, 1))) {
      return 'Tomorrow';
    }
    return format(date, 'EEEE, MMM d');
  }, [today]);

  return (
    <Panel>
      <Heading data-halo="heading">Upcoming Events</Heading>

      {eventsQuery.isLoading ? (
        <LoadingState>Loading...</LoadingState>
      ) : groupedEvents.length === 0 ? (
        <EmptyState>No upcoming events in the next 7 days</EmptyState>
      ) : (
        <EventsList>
          {groupedEvents.map(({ date, events }) => (
            <div key={date.toISOString()}>
              <DateDivider data-halo="body">
                {formatDateHeader(date)}
              </DateDivider>
              {events.map(event => (
                <EventCard key={event.id}>
                  <EventTime data-halo="body">
                    {formatEventTime(event.start_time, event.end_time, event.is_all_day)}
                  </EventTime>
                  <EventSummary data-halo="body">
                    {event.summary}
                  </EventSummary>
                  {event.location && (
                    <EventLocation data-halo="body">
                      📍 {event.location}
                    </EventLocation>
                  )}
                </EventCard>
              ))}
            </div>
          ))}
        </EventsList>
      )}
    </Panel>
  );
}