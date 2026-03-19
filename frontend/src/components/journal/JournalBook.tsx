import { useCallback, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import styled, { keyframes } from 'styled-components';

import edgeBleedLight from '../../assets/textures/edge_bleed_light.png';
import mistWashLight from '../../assets/textures/mist_wash_light.png';
import paperFiberLight from '../../assets/textures/paper_fiber_light.png';
import { useCalendarEvents } from '../../hooks/useCalendar';
import { useJournal } from '../../hooks/useJournal';
import { fetchJournalDay } from '../../services/api';

const bookFloat = keyframes`
  0% { transform: translateY(8px); opacity: 0; }
  100% { transform: translateY(0); opacity: 1; }
`;

const pageReveal = keyframes`
  0% { transform: translateY(12px); opacity: 0; }
  100% { transform: translateY(0); opacity: 1; }
`;

const BookShell = styled.div`
  position: relative;
  display: grid;
  --book-gap: clamp(16px, 2.5vw, 28px);
  gap: 0;
  grid-template-columns: minmax(200px, 0.95fr) var(--book-gap) minmax(260px, 1.2fr);
  max-width: 100%;
  overflow-x: hidden;
  padding: clamp(16px, 3vw, 28px);
  border-radius: 36px;
  background: ${({ theme }) => theme.colors.surfaceRaised};
  box-shadow: 0 30px 60px ${({ theme }) => theme.colors.overlay}, 0 10px 22px ${({ theme }) => theme.colors.overlay};
  isolation: isolate;
  animation: ${bookFloat} 0.5s ease-out;

  &::before {
    content: '';
    position: absolute;
    inset: 10px;
    border-radius: 28px;
    background: radial-gradient(circle at 20% 20%, ${({ theme }) => theme.colors.overlayHover}, transparent 55%),
      radial-gradient(circle at 80% 80%, ${({ theme }) => theme.colors.overlayHover}, transparent 55%);
    pointer-events: none;
    z-index: 0;
  }

  @media (max-width: 980px) {
    gap: var(--book-gap);
    grid-template-columns: 1fr;
  }
`;

const Spine = styled.div`
  grid-column: 2;
  align-self: center;
  justify-self: center;
  width: 16px;
  height: calc(100% - 24px);
  border-radius: 999px;
  background: ${({ theme }) =>
    theme.mode === 'dark'
      ? `linear-gradient(180deg, ${hexToRgba(theme.palette.neutral['700'], 0.8)}, ${hexToRgba(
          theme.palette.neutral['900'],
          0.9
        )})`
      : `linear-gradient(180deg, ${hexToRgba(theme.palette.neutral['50'], 0.8)}, ${hexToRgba(
          theme.palette.neutral['200'],
          0.9
        )})`};
  box-shadow: inset 0 0 8px ${({ theme }) => hexToRgba(theme.palette.neutral['900'], 0.2)};
  pointer-events: none;

  @media (max-width: 980px) {
    display: none;
  }
`;

const Page = styled.section`
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: 26px;
  padding: clamp(16px, 2.6vw, 26px);
  min-height: clamp(420px, 62vh, 640px);
  background: ${({ theme }) =>
    theme.mode === 'dark'
      ? `linear-gradient(180deg, rgba(30, 35, 48, 0.95) 0%, rgba(26, 30, 42, 0.97) 55%, rgba(22, 26, 36, 0.98) 100%)`
      : `linear-gradient(180deg, #f8eed7 0%, #f1e1c6 55%, #e7d2b2 100%)`};
  box-shadow: 0 24px 48px ${({ theme }) => theme.colors.overlay}, inset 0 1px 0 ${({ theme }) => theme.colors.overlayHover};
  animation: ${pageReveal} 0.55s ease-out;
  overflow: hidden;
  isolation: isolate;
  color: ${({ theme }) => theme.mode === 'dark' ? theme.colors.textPrimary : '#2f2118'};
  --page-ink: ${({ theme }) => theme.mode === 'dark' ? theme.colors.textPrimary : '#2f2118'};
  --page-ink-muted: ${({ theme }) => theme.mode === 'dark' ? theme.colors.textSecondary : 'rgba(47, 33, 24, 0.68)'};
  --page-border: ${({ theme }) => theme.mode === 'dark' ? theme.colors.borderSubtle : 'rgba(102, 78, 60, 0.22)'};
  --page-surface: ${({ theme }) => theme.mode === 'dark' ? theme.colors.overlay : 'rgba(255, 255, 255, 0.55)'};

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url(${paperFiberLight}), url(${mistWashLight});
    background-size: 420px 420px, cover;
    background-repeat: repeat, no-repeat;
    opacity: ${({ theme }) => theme.mode === 'dark' ? 0.12 : 0.35};
    mix-blend-mode: ${({ theme }) => theme.mode === 'dark' ? 'overlay' : 'multiply'};
    pointer-events: none;
    z-index: 0;
  }

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url(${edgeBleedLight});
    background-size: cover;
    background-repeat: no-repeat;
    opacity: ${({ theme }) => theme.mode === 'dark' ? 0.25 : 0.45};
    pointer-events: none;
    z-index: 0;
  }
`;

const PageContent = styled.div`
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  flex: 1;
`;

const PageHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-size: 0.8rem;
`;

const HeaderTitle = styled.span`
  color: var(--page-ink);
`;

const HeaderSub = styled.span`
  font-size: 0.7rem;
  opacity: 0.68;
  color: var(--page-ink-muted);
`;

const ToggleRow = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
`;

const ToggleButton = styled.button<{ $active: boolean }>`
  border: 1px solid var(--page-border);
  background: ${({ $active, theme }) => ($active ? theme.colors.overlayActive : 'transparent')};
  color: var(--page-ink);
  padding: 6px 10px;
  border-radius: 999px;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  cursor: pointer;
  opacity: ${({ $active }) => ($active ? 1 : 0.7)};

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Section = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
`;

const SectionHeaderRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
`;

const SectionTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.76;
  color: var(--page-ink);
`;

const CountPill = styled.span`
  font-size: 0.72rem;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--page-surface);
  border: 1px solid var(--page-border);
  color: var(--page-ink);
`;

const TaskList = styled.ul`
  list-style: none;
  margin: 0;
  padding: 0 6px 0 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: clamp(140px, 22vh, 230px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: ${({ theme }) => theme.colors.scrollThumb} transparent;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 999px;
  }
`;

const TaskItem = styled.li`
  padding: 8px 10px;
  border-radius: 14px;
  border: 1px dashed var(--page-border);
  background: var(--page-surface);
  font-size: 0.86rem;
  line-height: 1.4;
`;

const ItemTypeTag = styled.span<{ $kind: 'task' | 'event' }>`
  display: inline-block;
  font-size: 0.58rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 1px 6px;
  border-radius: 6px;
  margin-bottom: 4px;
  background: ${({ $kind }) => $kind === 'task' ? 'var(--page-ink-muted)' : 'var(--page-border)'};
  color: var(--page-surface);
  opacity: 0.7;
`;

const TaskMeta = styled.div`
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--page-ink-muted);
  margin-bottom: 4px;
`;

const TaskText = styled.div`
  color: var(--page-ink);
`;

const EmptyText = styled.div`
  font-size: 0.85rem;
  opacity: 0.7;
  color: var(--page-ink-muted);
`;

const CalendarList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: clamp(260px, 34vh, 360px);
  overflow-y: auto;
  padding-right: 6px;
  scrollbar-width: thin;
  scrollbar-color: ${({ theme }) => theme.colors.scrollThumb} transparent;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 999px;
  }
`;

const DayButton = styled.button<{ $active: boolean; $disabled: boolean }>`
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--page-border);
  background: ${({ $active, theme }) => ($active ? theme.colors.overlayActive : 'transparent')};
  color: var(--page-ink);
  padding: 10px 12px;
  border-radius: 14px;
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.88rem;
  cursor: ${({ $disabled }) => ($disabled ? 'not-allowed' : 'pointer')};
  opacity: ${({ $disabled }) => ($disabled ? 0.4 : 1)};

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const DayMarker = styled.span<{ $active: boolean }>`
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: ${({ $active }) => ($active ? 'var(--page-ink)' : 'transparent')};
  border: 1px solid var(--page-border);
`;

const DayLabel = styled.span`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const DayDate = styled.span`
  font-size: 0.82rem;
  opacity: 0.7;
`;

const WeekNav = styled.div`
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
`;

const WeekButton = styled.button`
  border: 1px solid var(--page-border);
  background: var(--page-surface);
  color: var(--page-ink);
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 0.75rem;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const EntryList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: clamp(180px, 26vh, 280px);
  overflow-y: auto;
  padding-right: 6px;
  scrollbar-width: thin;
  scrollbar-color: ${({ theme }) => theme.colors.scrollThumb} transparent;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 999px;
  }
`;

const EntryCard = styled.div`
  border-radius: 16px;
  padding: 10px 12px;
  background: var(--page-surface);
  border: 1px solid var(--page-border);
  font-size: 0.88rem;
  line-height: 1.45;
  white-space: pre-wrap;
`;

const EntryTime = styled.div`
  font-size: 0.72rem;
  opacity: 0.7;
  color: var(--page-ink-muted);
  margin-bottom: 4px;
`;

const JournalForm = styled.form`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const JournalTextarea = styled.textarea`
  min-height: 120px;
  max-height: 220px;
  resize: vertical;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--page-border);
  background-color: var(--page-surface);
  background-image: repeating-linear-gradient(
    180deg,
    var(--page-border) 0px,
    var(--page-border) 1px,
    transparent 1px,
    transparent 26px
  );
  color: var(--page-ink);
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.95rem;
  line-height: 1.5;
  box-shadow: inset 0 1px 3px ${({ theme }) => theme.colors.overlay};

  &:focus {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    border-color: var(--page-border);
  }
`;

const SubmitButton = styled.button`
  align-self: flex-end;
  border: none;
  border-radius: 14px;
  padding: 10px 16px;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.75rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  cursor: pointer;
  background: ${({ theme }) => theme.colors.accent};
  color: ${({ theme }) => theme.mode === 'dark' ? theme.colors.textPrimary : '#2a1d15'};
`;

const GroupList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: clamp(260px, 40vh, 420px);
  overflow-y: auto;
  padding-right: 6px;
  scrollbar-width: thin;
  scrollbar-color: ${({ theme }) => theme.colors.scrollThumb} transparent;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.scrollThumb};
    border-radius: 999px;
  }
`;

const GroupCard = styled.div`
  border-radius: 18px;
  padding: 12px 14px;
  background: var(--page-surface);
  border: 1px solid var(--page-border);
`;

const GroupTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 8px;
  color: var(--page-ink);
`;

const GroupItems = styled.ul`
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.88rem;
  line-height: 1.4;
`;

const GroupItem = styled.li`
  display: flex;
  align-items: flex-start;
  gap: 8px;
`;

const GroupItemTime = styled.span`
  flex: 0 0 auto;
  padding: 3px 7px;
  border-radius: 999px;
  border: 1px solid var(--page-border);
  background: var(--page-surface);
  color: var(--page-ink-muted);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
`;

const GroupItemText = styled.span`
  min-width: 0;
  color: var(--page-ink);
`;

const shimmerPulse = keyframes`
  0%, 100% { opacity: 0.5; }
  50% { opacity: 0.9; }
`;

const StatusMessage = styled.div`
  font-size: 0.85rem;
  opacity: 0.7;
  color: var(--page-ink-muted);
`;

const ProcessingMessage = styled(StatusMessage)`
  animation: ${shimmerPulse} 2s ease-in-out infinite;

  @media (prefers-reduced-motion: reduce) {
    animation: none;
  }
`;

const PageNav = styled.div`
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
`;

const PageNavButton = styled.button`
  width: 44px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid var(--page-border);
  background: var(--page-surface);
  box-shadow: inset 0 1px 0 ${({ theme }) => theme.colors.overlayHover}, 0 6px 12px ${({ theme }) => theme.colors.overlay};
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--page-ink);
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: inset 0 1px 0 ${({ theme }) => theme.colors.overlayActive}, 0 8px 16px ${({ theme }) => theme.colors.overlay};
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const ArrowIcon = styled.span<{ $direction: 'left' | 'right' }>`
  width: 10px;
  height: 10px;
  border-top: 2px solid var(--page-ink);
  border-right: 2px solid var(--page-ink);
  transform: ${({ $direction }) => ($direction === 'left' ? 'rotate(-135deg)' : 'rotate(45deg)')};
`;

export function JournalBook() {
  const today = useMemo(() => startOfDay(new Date()), []);
  const [leftMode, setLeftMode] = useState<'completed' | 'calendar'>('completed');
  const [weekStart, setWeekStart] = useState(() => getWeekStart(today));
  const [selectedDate, setSelectedDate] = useState(today);
  const [entryText, setEntryText] = useState('');

  const weekStartKey = formatDateKey(weekStart);
  const selectedKey = formatDateKey(selectedDate);
  const todayKey = formatDateKey(today);

  const { dayQuery, weekQuery, createEntry, isSavingEntry, timeZone } = useJournal(
    selectedKey,
    weekStartKey
  );

  const todayQuery = useQuery({
    queryKey: ['journal', 'day', todayKey, timeZone],
    queryFn: () => fetchJournalDay(todayKey, timeZone),
    enabled: selectedKey !== todayKey,
    refetchOnWindowFocus: true,
    refetchInterval: 60 * 1000,
    refetchIntervalInBackground: false
  });

  const todayEventsQuery = useCalendarEvents(
    today.toISOString(),
    endOfDay(today).toISOString(),
    true,
    {
      refetchOnWindowFocus: true,
      refetchInterval: 60 * 1000,
      refetchIntervalInBackground: false
    }
  );

  const weekDays = useMemo(() => buildWeekDays(weekStart), [weekStart]);
  const dayStatusMap = useMemo(() => {
    const map = new Map<string, { has_entries: boolean; has_summary: boolean; completed_count: number }>();
    weekQuery.data?.days.forEach((day) => {
      map.set(day.local_date, day);
    });
    return map;
  }, [weekQuery.data]);

  const isTodaySelected = selectedKey === todayKey;
  const dayData = dayQuery.data;
  const todayData = isTodaySelected ? dayData : todayQuery.data;
  const completedItems = dayData?.completed_items ?? [];
  const todayCompletedItems = todayData?.completed_items ?? [];
  const endedCalendarEvents = useMemo(() => {
    const events = todayEventsQuery.eventsQuery.data?.events ?? [];
    const startBoundary = today.getTime();
    const endBoundary = addDays(today, 1).getTime();
    const now = Date.now();
    return events
      .filter((event) => Boolean(event.start_time && event.end_time))
      .filter((event) => !event.todo_id)
      .filter((event) => {
        const startTime = new Date(event.start_time as string).getTime();
        const endTime = new Date(event.end_time as string).getTime();
        if (Number.isNaN(startTime) || Number.isNaN(endTime)) return false;
        if (startTime < startBoundary || startTime >= endBoundary) return false;
        return endTime <= now;
      })
      .sort(
        (left, right) =>
          new Date(left.start_time as string).getTime() - new Date(right.start_time as string).getTime()
      );
  }, [todayEventsQuery.eventsQuery.data, today]);
  const entries = dayData?.entries ?? [];
  const summaryGroups = dayData?.summary?.groups ?? [];
  const canGoNextDay = selectedKey < todayKey;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = entryText.trim();
    if (!trimmed) return;
    await createEntry(trimmed);
    setEntryText('');
  };

  const navTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const pendingDateRef = useRef<Date | null>(null);

  const applyNavigation = useCallback((nextDate: Date) => {
    const nextKey = formatDateKey(nextDate);
    setSelectedDate(nextDate);

    const nextWeekStart = getWeekStart(nextDate);
    if (formatDateKey(nextWeekStart) !== weekStartKey) {
      setWeekStart(nextWeekStart);
    }

    if (nextKey === todayKey) {
      setLeftMode('completed');
    } else if (leftMode === 'completed') {
      setLeftMode('calendar');
    }
  }, [weekStartKey, todayKey, leftMode]);

  const handleNavigateDay = (delta: number) => {
    const base = pendingDateRef.current ?? selectedDate;
    const nextDate = addDays(base, delta);
    const nextKey = formatDateKey(nextDate);
    if (delta > 0 && nextKey > todayKey) return;

    pendingDateRef.current = nextDate;
    clearTimeout(navTimerRef.current);
    navTimerRef.current = setTimeout(() => {
      pendingDateRef.current = null;
      applyNavigation(nextDate);
    }, 200);

    if (nextKey === todayKey) {
      setLeftMode('completed');
    } else if (leftMode === 'completed') {
      setLeftMode('calendar');
    }
  };

  const showNextWeek = weekStart < getWeekStart(today);

  return (
    <BookShell>
      <Page>
        <PageContent>
          <PageHeader>
            <HeaderTitle data-halo="heading">Journal</HeaderTitle>
            <HeaderSub>{formatWeekLabel(weekStart)}</HeaderSub>
          </PageHeader>
          <ToggleRow>
            <ToggleButton $active={leftMode === 'completed'} onClick={() => setLeftMode('completed')}>
              Done Today
            </ToggleButton>
            <ToggleButton $active={leftMode === 'calendar'} onClick={() => setLeftMode('calendar')}>
              Calendar
            </ToggleButton>
          </ToggleRow>
          {leftMode === 'completed' ? (
            <>
              <Section>
                <SectionHeaderRow>
                  <SectionTitle>Completed Today</SectionTitle>
                  <CountPill>{todayCompletedItems.length} done</CountPill>
                </SectionHeaderRow>
                {todayCompletedItems.length === 0 ? (
                  <EmptyText>No completed to-dos yet.</EmptyText>
                ) : (
                  <TaskList>
                    {todayCompletedItems.map((item) => (
                      <TaskItem key={item.id}>
                        <ItemTypeTag $kind="task">Task</ItemTypeTag>
                        <TaskMeta>{formatOptionalTime(item.completed_at_utc)}</TaskMeta>
                        <TaskText>{item.text}</TaskText>
                      </TaskItem>
                    ))}
                  </TaskList>
                )}
              </Section>
              <Section>
                <SectionHeaderRow>
                  <SectionTitle>Calendar (Ended)</SectionTitle>
                  <CountPill>{endedCalendarEvents.length} events</CountPill>
                </SectionHeaderRow>
                {todayEventsQuery.eventsQuery.isLoading ? (
                  <EmptyText>Loading calendar...</EmptyText>
                ) : endedCalendarEvents.length === 0 ? (
                  <EmptyText>No calendar events have ended yet.</EmptyText>
                ) : (
                  <TaskList>
                    {endedCalendarEvents.map((event) => (
                      <TaskItem key={event.id}>
                        <ItemTypeTag $kind="event">Event</ItemTypeTag>
                        {event.is_all_day
                          ? 'All day'
                          : `${formatTime(event.start_time as string)} - ${formatTime(event.end_time as string)}`}
                        {event.summary ? ` · ${event.summary}` : null}
                      </TaskItem>
                    ))}
                  </TaskList>
                )}
              </Section>
            </>
          ) : (
            <Section>
              <WeekNav>
                <WeekButton
                  type="button"
                  onClick={() => {
                    const nextStart = addDays(weekStart, -7);
                    setWeekStart(nextStart);
                    setSelectedDate(nextStart);
                  }}
                >
                  Prev Week
                </WeekButton>
                <WeekButton
                  type="button"
                  onClick={() => {
                    const nextStart = addDays(weekStart, 7);
                    setWeekStart(nextStart);
                    setSelectedDate(nextStart);
                  }}
                  disabled={!showNextWeek}
                >
                  Next Week
                </WeekButton>
              </WeekNav>
              <CalendarList>
                {weekDays.map((day) => {
                  const key = formatDateKey(day);
                  const status = dayStatusMap.get(key);
                  const isFuture = key > todayKey;
                  return (
                    <DayButton
                      key={key}
                      type="button"
                      $active={key === selectedKey}
                      $disabled={isFuture}
                      onClick={() => {
                        if (!isFuture) setSelectedDate(day);
                      }}
                    >
                      <DayMarker $active={Boolean(status?.has_entries || status?.has_summary || status?.completed_count)} />
                      <DayLabel>{formatDayLabel(day)}</DayLabel>
                      <DayDate>{formatDayShort(day)}</DayDate>
                    </DayButton>
                  );
                })}
              </CalendarList>
            </Section>
          )}
        </PageContent>
      </Page>
      <Spine />
      <Page>
        <PageContent>
          <PageHeader>
            <HeaderTitle data-halo="heading">
              {isTodaySelected ? 'Today' : formatFullDate(selectedDate)}
            </HeaderTitle>
            <HeaderSub>{isTodaySelected ? 'Write in your journal' : 'Day summary'}</HeaderSub>
          </PageHeader>
          {dayQuery.isLoading ? (
            <StatusMessage>Loading journal page...</StatusMessage>
          ) : dayQuery.error ? (
            <StatusMessage>Could not load this day yet.</StatusMessage>
          ) : isTodaySelected ? (
            <>
              <Section>
                <SectionHeaderRow>
                  <SectionTitle>Completed Today</SectionTitle>
                  <CountPill>{completedItems.length} done</CountPill>
                </SectionHeaderRow>
                {completedItems.length === 0 ? (
                  <EmptyText>No completed to-dos yet.</EmptyText>
                ) : (
                  <TaskList>
                    {completedItems.map((item) => (
                      <TaskItem key={item.id}>
                        <ItemTypeTag $kind="task">Task</ItemTypeTag>
                        <TaskMeta>{formatOptionalTime(item.completed_at_utc)}</TaskMeta>
                        <TaskText>{item.text}</TaskText>
                      </TaskItem>
                    ))}
                  </TaskList>
                )}
              </Section>
              <Section>
                <SectionTitle>Earlier Entries</SectionTitle>
                {entries.length === 0 ? (
                  <EmptyText>Your entries will appear here as you write.</EmptyText>
                ) : (
                  <EntryList>
                    {entries.map((entry) => (
                      <EntryCard key={entry.id}>
                        <EntryTime>{formatTime(entry.created_at)}</EntryTime>
                        <div>{entry.text}</div>
                      </EntryCard>
                    ))}
                  </EntryList>
                )}
              </Section>
              <Section>
                <SectionTitle>Write</SectionTitle>
                <JournalForm onSubmit={handleSubmit}>
                  <JournalTextarea
                    value={entryText}
                    onChange={(event) => setEntryText(event.target.value)}
                    placeholder="What did you do today?"
                  />
                  <SubmitButton type="submit" disabled={isSavingEntry}>
                    {isSavingEntry ? 'Saving...' : 'Add Entry'}
                  </SubmitButton>
                </JournalForm>
              </Section>
            </>
          ) : (
            <>
              {dayData?.status === 'error' ? (
                <ProcessingMessage>Summary is still processing. Check back soon.</ProcessingMessage>
              ) : summaryGroups.length === 0 ? (
                <StatusMessage>No accomplishments were logged for this day.</StatusMessage>
              ) : (
                <GroupList>
                  {summaryGroups.map((group) => (
                    <GroupCard key={group.title}>
                      <GroupTitle>{group.title}</GroupTitle>
                      <GroupItems>
                        {group.items.map((item, index) => (
                          <GroupItem key={`${group.title}-${index}`}>
                            {item.time_label ? <GroupItemTime>{item.time_label}</GroupItemTime> : null}
                            <GroupItemText>{item.text}</GroupItemText>
                          </GroupItem>
                        ))}
                      </GroupItems>
                    </GroupCard>
                  ))}
                </GroupList>
              )}
            </>
          )}
          <PageNav>
            <PageNavButton type="button" onClick={() => handleNavigateDay(-1)} aria-label="Previous day">
              <ArrowIcon $direction="left" />
            </PageNavButton>
            <PageNavButton
              type="button"
              onClick={() => handleNavigateDay(1)}
              aria-label="Next day"
              disabled={!canGoNextDay}
            >
              <ArrowIcon $direction="right" />
            </PageNavButton>
          </PageNav>
        </PageContent>
      </Page>
    </BookShell>
  );
}

const formatDateKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const formatDayLabel = (date: Date) => date.toLocaleDateString(undefined, { weekday: 'long' });

const formatDayShort = (date: Date) => date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

const formatFullDate = (date: Date) =>
  date.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

const formatWeekLabel = (date: Date) => {
  const start = formatDayShort(date);
  const end = formatDayShort(addDays(date, 6));
  return `${start} - ${end}`;
};

const formatTime = (value: string) =>
  new Date(value).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

const formatOptionalTime = (value: string | null) => (value ? formatTime(value) : 'Time unknown');

const startOfDay = (date: Date) => {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
};

const endOfDay = (date: Date) => {
  const next = new Date(date);
  next.setHours(23, 59, 59, 999);
  return next;
};

const getWeekStart = (date: Date) => {
  const next = startOfDay(date);
  const day = next.getDay();
  next.setDate(next.getDate() - day);
  return next;
};

const addDays = (date: Date, days: number) => {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
};

const buildWeekDays = (weekStart: Date) =>
  Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));

const hexToRgba = (hex: string, alpha: number) => {
  const cleaned = hex.replace('#', '');
  if (cleaned.length !== 6) return hex;
  const r = parseInt(cleaned.slice(0, 2), 16);
  const g = parseInt(cleaned.slice(2, 4), 16);
  const b = parseInt(cleaned.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};
