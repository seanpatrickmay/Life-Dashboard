import { useEffect, useMemo, useState } from 'react';
import styled from 'styled-components';
import { CalendarWeekView, type CalendarItem } from '../components/calendar/CalendarWeekView';
import { CalendarDetailDrawer } from '../components/calendar/CalendarDetailDrawer';
import { useCalendarEvents, useCalendarStatus, useCalendars } from '../hooks/useCalendar';
import { useTodos } from '../hooks/useTodos';
import { Card } from '../components/common/Card';
import { fadeUp, reducedMotion } from '../styles/animations';
import type { CalendarEvent, TodoItem } from '../services/api';

const Layout = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const CalendarShell = styled.div`
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  animation: ${fadeUp} 0.5s ease both;
  ${reducedMotion}
`;


const HeaderRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
`;

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 1rem;
`;

const ControlGrid = styled.div`
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(240px, 0.9fr) minmax(300px, 1.2fr);

  @media (max-width: 980px) {
    grid-template-columns: 1fr;
  }
`;

const CardTitle = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.16em;
`;

const StatusText = styled.p`
  margin: 0;
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const SubtleText = styled.span`
  font-size: 0.72rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const ButtonRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`;

const ActionButton = styled.button<{ $primary?: boolean }>`
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-family: ${({ theme }) => theme.fonts.heading};
  cursor: pointer;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme, $primary }) =>
    $primary ? theme.colors.overlayActive : theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textPrimary};
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: background 0.15s ease;

  &:hover {
    background: ${({ theme }) => theme.colors.overlayActive};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const CalendarList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const CalendarRow = styled.label<{ $disabled?: boolean }>`
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 12px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  opacity: ${({ $disabled }) => ($disabled ? 0.6 : 1)};
`;

const CalendarToggle = styled.input`
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;

  &::after {
    content: '✓';
    font-size: 0.72rem;
    color: ${({ theme }) => theme.colors.textPrimary};
    opacity: 0;
    transform: scale(0.7);
    transition: opacity 0.2s ease, transform 0.2s ease;
  }

  &:checked {
    background: ${({ theme }) => theme.palette.bloom['200']};
    border-color: ${({ theme }) => theme.palette.bloom['200']};
  }

  &:checked::after {
    opacity: 1;
    transform: scale(1);
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.palette.pond['200']};
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const CalendarName = styled.span`
  font-size: 0.82rem;
`;

const CalendarBadge = styled.span`
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const CalendarSurface = styled.div`
  border-radius: 30px;
  padding: 18px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  box-shadow: ${({ theme }) => theme.shadows.soft};
  display: flex;
  flex-direction: column;
  width: 100%;
  flex: 1;
  min-height: 400px;
  overflow: hidden;
  ${reducedMotion}
`;

const ErrorText = styled.p`
  margin: 0;
  font-size: 0.78rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const EmptyState = styled.p`
  margin: 0;
  font-size: 0.78rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const ControlsToggle = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  background: ${({ theme }) => theme.colors.overlay};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 8px;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 6px 12px;
  cursor: pointer;
  transition: background 0.15s ease;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);

  &:hover {
    background: ${({ theme }) => theme.colors.overlayActive};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const ControlsWrapper = styled.div<{ $open: boolean }>`
  display: grid;
  grid-template-rows: ${({ $open }) => ($open ? '1fr' : '0fr')};
  transition: grid-template-rows 0.3s ease;

  @media (prefers-reduced-motion: reduce) {
    transition-duration: 0.01ms;
  }
`;

const ControlsInner = styled.div`
  overflow: hidden;
`;

const CardContentLayout = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

type RecurrenceScope = 'occurrence' | 'future' | 'series';

export function CalendarPage() {
  const { todosQuery, updateTodo } = useTodos();
  const statusQuery = useCalendarStatus();
  const { calendarsQuery, updateSelection } = useCalendars();
  const today = startOfDay(new Date());
  const days = buildRollingDays(today);
  const windowStart = startOfDay(addDays(today, -1));
  const windowEnd = endOfDay(addDays(today, 5));
  const eventsQuery = useCalendarEvents(
    windowStart.toISOString(),
    windowEnd.toISOString(),
    Boolean(statusQuery.data?.connected)
  );

  const [selectedItem, setSelectedItem] = useState<CalendarItem | null>(null);
  const [recurrenceScope, setRecurrenceScope] = useState<RecurrenceScope>('occurrence');
  const [controlsOpen, setControlsOpen] = useState(false);

  useEffect(() => {
    if (selectedItem?.kind === 'event') {
      const event = selectedItem.data as CalendarEvent;
      if (event.recurring_event_id) {
        setRecurrenceScope('occurrence');
      }
    }
  }, [selectedItem]);

  const todoEntries = useMemo(
    () => (todosQuery.data ?? []).filter((todo) => !todo.completed && todo.deadline_utc),
    [todosQuery.data]
  );
  const todoItems = useMemo(() => buildTodoItems(todoEntries), [todoEntries]);

  const eventItems = useMemo(() => {
    const events = eventsQuery.eventsQuery.data?.events ?? [];
    const deduped = events.filter((event) => !event.todo_id);
    return buildEventItems(deduped);
  }, [eventsQuery.eventsQuery.data]);

  const timedItems = [...todoItems.timed, ...eventItems.timed];
  const allDayItems = [...todoItems.allDay, ...eventItems.allDay];

  const status = statusQuery.data;
  const calendars = calendarsQuery.data?.calendars ?? [];

  const handleConnect = () => {
    const redirect = encodeURIComponent(`${window.location.origin}/calendar`);
    window.location.href = `/api/calendar/google/login?redirect=${redirect}`;
  };

  const handleToggleCalendar = async (calendar: { google_id: string; selected: boolean; is_life_dashboard: boolean }) => {
    if (calendar.is_life_dashboard) return;
    const current = new Set(calendars.filter((cal) => cal.selected).map((cal) => cal.google_id));
    if (calendar.selected) {
      current.delete(calendar.google_id);
    } else {
      current.add(calendar.google_id);
    }
    await updateSelection(Array.from(current));
  };

  const getEventScope = (item: CalendarItem) => {
    if (item.kind !== 'event') return 'occurrence';
    const event = item.data as CalendarEvent;
    if (!event.recurring_event_id) return 'occurrence';
    if (selectedItem?.key === item.key) {
      return recurrenceScope;
    }
    return 'occurrence';
  };

  const handleMoveItem = async (item: CalendarItem, start: Date, end: Date) => {
    if (item.kind === 'todo') {
      const todo = item.data as TodoItem;
      await updateTodo({
        id: todo.id,
        deadline_utc: end.toISOString(),
        deadline_is_date_only: false
      });
      return;
    }
    const event = item.data as CalendarEvent;
    await eventsQuery.updateCalendarEvent({
      id: event.id,
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      scope: getEventScope(item),
      is_all_day: false
    });
  };

  const handleResizeItem = async (item: CalendarItem, start: Date, end: Date) => {
    await handleMoveItem(item, start, end);
  };

  const handleMoveAllDayItem = async (item: CalendarItem, targetDay: Date) => {
    if (item.kind === 'todo') {
      const todo = item.data as TodoItem;
      const due = endOfDay(targetDay);
      await updateTodo({
        id: todo.id,
        deadline_utc: due.toISOString(),
        deadline_is_date_only: true
      });
      return;
    }
    const event = item.data as CalendarEvent;
    const start = startOfDay(targetDay);
    const end = addDays(start, 1);
    await eventsQuery.updateCalendarEvent({
      id: event.id,
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      scope: getEventScope(item),
      is_all_day: true
    });
  };


  return (
    <Layout>
      <CalendarShell>
        <HeaderRow>
          <Title data-halo="heading">Calendar</Title>
          <ButtonRow>
            <ControlsToggle onClick={() => setControlsOpen(prev => !prev)}>
              {controlsOpen ? 'Hide settings' : 'Settings'}
            </ControlsToggle>
            {status?.connected ? (
              <ActionButton type="button" onClick={() => eventsQuery.syncCalendar()} $primary aria-label="Sync calendar">
                Sync now
              </ActionButton>
            ) : null}
            {!status?.connected || status?.requires_reauth ? (
              <ActionButton type="button" onClick={handleConnect} $primary>
                {status?.requires_reauth ? 'Reconnect' : 'Connect Google'}
              </ActionButton>
            ) : null}
          </ButtonRow>
        </HeaderRow>

        <ControlsWrapper $open={controlsOpen}>
          <ControlsInner>
            <ControlGrid>
              <Card>
                <CardContentLayout>
                  <CardTitle data-halo="heading">Google Calendar</CardTitle>
                  {status?.connected ? (
                    <>
                      <StatusText>Connected as {status.account_email ?? 'your account'}.</StatusText>
                      <SubtleText>
                        Last sync {status.last_sync_at ? formatDateTime(new Date(status.last_sync_at)) : 'not yet'}
                      </SubtleText>
                    </>
                  ) : (
                    <StatusText>Connect to sync events and write todo blocks.</StatusText>
                  )}
                  {eventsQuery.isSyncing ? <SubtleText>Syncing…</SubtleText> : null}
                </CardContentLayout>
              </Card>
              <Card>
                <CardContentLayout>
                  <CardTitle data-halo="heading">Calendars</CardTitle>
                  {status?.connected ? (
                    <CalendarList>
                      {calendars.map((calendar) => (
                        <CalendarRow
                          key={calendar.google_id}
                          $disabled={calendar.is_life_dashboard}
                        >
                          <CalendarToggle
                            type="checkbox"
                            checked={calendar.selected}
                            disabled={calendar.is_life_dashboard}
                            onChange={() => handleToggleCalendar(calendar)}
                          />
                          <CalendarName>{calendar.summary}</CalendarName>
                          {calendar.is_life_dashboard ? <CalendarBadge>Life Dashboard</CalendarBadge> : null}
                        </CalendarRow>
                      ))}
                      {!calendars.length ? <EmptyState>No calendars found yet.</EmptyState> : null}
                    </CalendarList>
                  ) : (
                    <EmptyState>Connect Google Calendar to pick calendars.</EmptyState>
                  )}
                </CardContentLayout>
              </Card>
            </ControlGrid>
          </ControlsInner>
        </ControlsWrapper>

        <CalendarSurface>
          {eventsQuery.eventsQuery.error ? (
            <ErrorText>Could not load calendar events right now.</ErrorText>
          ) : null}
          <CalendarWeekView
            days={days}
            timedItems={timedItems}
            allDayItems={allDayItems}
            mutedDayIndex={0}
            onSelectItem={setSelectedItem}
            onMoveItem={handleMoveItem}
            onResizeItem={handleResizeItem}
            onMoveAllDayItem={handleMoveAllDayItem}
          />
        </CalendarSurface>

        <CalendarDetailDrawer
          open={Boolean(selectedItem)}
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
          recurrenceScope={recurrenceScope}
          onChangeScope={setRecurrenceScope}
        />
      </CalendarShell>

    </Layout>
  );
}

const buildRollingDays = (anchor: Date) => {
  const base = startOfDay(anchor);
  const days: Date[] = [];
  for (let offset = -1; offset <= 5; offset += 1) {
    days.push(addDays(base, offset));
  }
  return days;
};

const buildTodoItems = (todos: TodoItem[]) => {
  const timed: CalendarItem[] = [];
  const allDay: CalendarItem[] = [];
  todos.forEach((todo) => {
    if (!todo.deadline_utc) return;
    const deadline = new Date(todo.deadline_utc);
    if (todo.deadline_is_date_only) {
      const start = startOfDay(deadline);
      const end = endOfDay(deadline);
      allDay.push({
        key: `todo-${todo.id}`,
        kind: 'todo',
        title: todo.text,
        start,
        end,
        allDay: true,
        priority: 0,
        data: todo
      });
      return;
    }
    const end = deadline;
    const start = new Date(end.getTime() - 30 * 60000);
    timed.push({
      key: `todo-${todo.id}`,
      kind: 'todo',
      title: todo.text,
      start,
      end,
      allDay: false,
      priority: 0,
      data: todo
    });
  });
  return { timed, allDay };
};

const buildEventItems = (events: CalendarEvent[]) => {
  const timed: CalendarItem[] = [];
  const allDay: CalendarItem[] = [];
  events.forEach((event) => {
    if (!event.start_time || !event.end_time) return;
    const segments = splitEventSegments(event);
    segments.forEach((segment) => {
      const item: CalendarItem = {
        key: `event-${event.id}-${segment.key}`,
        kind: 'event',
        title: event.summary || 'Untitled event',
        start: segment.start,
        end: segment.end,
        allDay: segment.allDay,
        isRecurring: Boolean(event.recurring_event_id),
        isFree: event.transparency === 'transparent',
        priority: event.calendar_is_life_dashboard ? 0 : 1,
        data: event
      };
      if (segment.allDay) {
        allDay.push(item);
      } else {
        timed.push(item);
      }
    });
  });
  return { timed, allDay };
};

const splitEventSegments = (event: CalendarEvent) => {
  const start = new Date(event.start_time ?? '');
  const end = new Date(event.end_time ?? '');
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return [];
  }
  if (event.is_all_day) {
    const segments = [];
    const cursor = startOfDay(start);
    const endDate = startOfDay(end);
    let current = cursor;
    while (current < endDate) {
      segments.push({
        key: toDayKey(current),
        start: startOfDay(current),
        end: endOfDay(current),
        allDay: true
      });
      current = addDays(current, 1);
    }
    return segments;
  }
  const adjustedEnd = adjustMidnightEnd(start, end);
  if (isSameDay(start, adjustedEnd)) {
    return [
      {
        key: toDayKey(start),
        start,
        end: adjustedEnd,
        allDay: false
      }
    ];
  }
  const segments = [];
  let current = startOfDay(start);
  const lastDay = startOfDay(adjustedEnd);
  while (current <= lastDay) {
    if (isSameDay(current, start)) {
      segments.push({
        key: toDayKey(current),
        start,
        end: endOfDay(current),
        allDay: false
      });
    } else if (isSameDay(current, adjustedEnd)) {
      segments.push({
        key: toDayKey(current),
        start: startOfDay(current),
        end: adjustedEnd,
        allDay: false
      });
    } else {
      segments.push({
        key: toDayKey(current),
        start: startOfDay(current),
        end: endOfDay(current),
        allDay: false
      });
    }
    current = addDays(current, 1);
  }
  return segments;
};

const startOfDay = (date: Date) => {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
};

const endOfDay = (date: Date) => {
  const next = new Date(date);
  next.setHours(23, 59, 0, 0);
  return next;
};

const addDays = (date: Date, days: number) => {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
};

const isSameDay = (left: Date, right: Date) =>
  left.getFullYear() === right.getFullYear() &&
  left.getMonth() === right.getMonth() &&
  left.getDate() === right.getDate();

const adjustMidnightEnd = (start: Date, end: Date) => {
  if (isSameDay(start, end)) return end;
  if (end.getHours() === 0 && end.getMinutes() === 0 && end.getSeconds() === 0) {
    const adjusted = new Date(end);
    adjusted.setMinutes(adjusted.getMinutes() - 1);
    return adjusted;
  }
  return end;
};

const toDayKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const formatDateTime = (date: Date) =>
  date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
