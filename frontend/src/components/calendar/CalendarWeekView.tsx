import { useEffect, useMemo, useRef, useState, type DragEvent, type PointerEvent, type UIEvent } from 'react';
import styled, { css } from 'styled-components';
import type { CalendarEvent, TodoItem } from '../../services/api';

export type CalendarItem = {
  key: string;
  kind: 'event' | 'todo';
  title: string;
  start: Date;
  end: Date;
  allDay: boolean;
  priority?: number;
  isRecurring?: boolean;
  isFree?: boolean;
  data: CalendarEvent | TodoItem;
};

type Props = {
  days: Date[];
  timedItems: CalendarItem[];
  allDayItems: CalendarItem[];
  mutedDayIndex?: number;
  onSelectItem?: (item: CalendarItem) => void;
  onMoveItem?: (item: CalendarItem, start: Date, end: Date) => void;
  onResizeItem?: (item: CalendarItem, start: Date, end: Date) => void;
  onMoveAllDayItem?: (item: CalendarItem, targetDay: Date) => void;
};

const TIMED_CARD_HEIGHT = 66;
const TIMED_CARD_GAP = 10;
const ALL_DAY_CARD_HEIGHT = 30;
const ALL_DAY_CARD_GAP = 6;
const ALL_DAY_SECTION_HEIGHT = 86;
const RESIZE_STEP_MINUTES = 15;
const RESIZE_STEP_PX = 10;
const MIN_EVENT_DURATION_MINUTES = 15;

const WeekGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 12px;
  width: 100%;
  height: 100%;
`;

const DayColumn = styled.div<{ $muted: boolean }>`
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  padding: 12px;
  border-radius: 20px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => hexToRgba(theme.colors.textPrimary, theme.mode === 'dark' ? 0.08 : 0.04)};
  opacity: ${({ $muted }) => ($muted ? 0.6 : 1)};
`;

const DayHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 0.7rem;
`;

const DayName = styled.span`
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const DayDate = styled.span`
  font-size: 0.68rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const AllDaySection = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: ${ALL_DAY_SECTION_HEIGHT}px;
  max-height: ${ALL_DAY_SECTION_HEIGHT}px;
`;

const AllDayLabel = styled.span`
  font-size: 0.6rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const AllDayList = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${ALL_DAY_CARD_GAP}px;
  overflow: hidden;
  flex: 1;
`;

const TimedSection = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  flex: 1;
`;

const TimedList = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${TIMED_CARD_GAP}px;
  overflow-y: auto;
  min-height: 0;
  flex: 1;
  padding-right: 4px;
`;

const MoreIndicator = styled.div`
  font-size: 0.66rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
  text-align: center;
`;

const CardButton = styled.div<{
  $kind: 'event' | 'todo';
  $allDay: boolean;
  $stacked: boolean;
  $dragging: boolean;
}>`
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 6px;
  padding: ${({ $allDay }) => ($allDay ? '6px 8px' : '8px 10px')};
  min-height: ${({ $allDay }) => ($allDay ? `${ALL_DAY_CARD_HEIGHT}px` : `${TIMED_CARD_HEIGHT}px`)};
  border-radius: 14px;
  border: 1px ${({ $kind }) => ($kind === 'todo' ? 'dashed' : 'solid')}
    ${({ theme, $kind }) => ($kind === 'todo' ? theme.palette.lilac['200'] : theme.colors.borderSubtle)};
  background: ${({ theme }) => hexToRgba(theme.colors.textPrimary, theme.mode === 'dark' ? 0.12 : 0.05)};
  cursor: ${({ $dragging }) => ($dragging ? 'grabbing' : 'grab')};
  opacity: ${({ $dragging }) => ($dragging ? 0.55 : 1)};
  transition: border-color 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
  user-select: none;

  ${({ $stacked, theme }) =>
    $stacked
      ? css`
          box-shadow:
            3px 3px 0 ${hexToRgba(theme.palette.neutral['900'], 0.06)},
            6px 6px 0 ${hexToRgba(theme.palette.neutral['900'], 0.04)};
        `
      : css`
          box-shadow: 0 6px 14px ${hexToRgba(theme.palette.neutral['900'], 0.08)};
        `};

  &:hover {
    border-color: ${({ theme, $kind }) =>
      $kind === 'todo' ? theme.palette.lilac['200'] : theme.colors.textSecondary};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.palette.pond['200']};
    outline-offset: 2px;
  }
`;

const TimeRow = styled.div`
  display: flex;
  justify-content: flex-end;
  align-items: center;
  width: 100%;
`;

const CardTitle = styled.span`
  font-size: 0.78rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  line-height: 1.2;
  white-space: normal;
  word-break: break-word;
`;

const TimeBadge = styled.span`
  font-size: 0.68rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
`;

const ResizeHandle = styled.div`
  position: absolute;
  right: 6px;
  bottom: 4px;
  width: 18px;
  height: 10px;
  border-radius: 6px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => hexToRgba(theme.colors.textPrimary, 0.08)};
  cursor: ns-resize;
`;

const DropZone = styled.div<{ $active: boolean }>`
  border-radius: 16px;
  padding: 2px;
  transition: background 0.2s ease;
  background: ${({ $active, theme }) =>
    $active ? hexToRgba(theme.colors.textPrimary, theme.mode === 'dark' ? 0.16 : 0.08) : 'transparent'};
`;

type DayColumnProps = {
  day: Date;
  muted: boolean;
  timedItems: CalendarItem[];
  allDayItems: CalendarItem[];
  draggingKey: string | null;
  onSelectItem?: (item: CalendarItem) => void;
  onDragStart: (item: CalendarItem) => void;
  onDragEnd: () => void;
  onDropTimed: (day: Date) => void;
  onDropAllDay: (day: Date) => void;
  onResizeItem?: (item: CalendarItem, start: Date, end: Date) => void;
};

type OverflowSettings = {
  itemCount: number;
  itemHeight: number;
  gap: number;
  trackScroll: boolean;
};

const useOverflowIndicator = ({ itemCount, itemHeight, gap, trackScroll }: OverflowSettings) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [visibleCount, setVisibleCount] = useState(itemCount);
  const [scrollTop, setScrollTop] = useState(0);
  const [averageHeight, setAverageHeight] = useState(itemHeight + gap);
  const [clientHeight, setClientHeight] = useState(0);
  const [scrollHeight, setScrollHeight] = useState(0);
  const rowSize = itemHeight + gap;

  const updateVisibleCount = () => {
    const element = containerRef.current;
    if (!element) {
      setVisibleCount(itemCount);
      return;
    }
    if (!itemCount) {
      setVisibleCount(0);
      setAverageHeight(rowSize);
      setClientHeight(element.clientHeight);
      setScrollHeight(element.scrollHeight);
      return;
    }
    const height = element.clientHeight;
    const contentHeight = element.scrollHeight;
    // Use average card height so wrapped titles can grow without breaking the overflow count.
    const average = contentHeight > 0 ? contentHeight / itemCount : rowSize;
    const count = Math.max(1, Math.floor(height / average));
    setVisibleCount(Math.min(itemCount, count));
    setAverageHeight(average);
    setClientHeight(height);
    setScrollHeight(contentHeight);
  };

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    setScrollTop(event.currentTarget.scrollTop);
  };

  useEffect(() => {
    updateVisibleCount();
  }, [itemCount, rowSize, gap]);

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return undefined;
    const element = containerRef.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(() => updateVisibleCount());
    observer.observe(element);
    return () => observer.disconnect();
  }, [itemCount, rowSize, gap]);

  const remaining = trackScroll && averageHeight > 0
    ? Math.max(0, Math.ceil((scrollHeight - scrollTop - clientHeight) / averageHeight))
    : Math.max(0, itemCount - visibleCount);

  return {
    containerRef,
    visibleCount,
    remaining,
    onScroll: trackScroll ? handleScroll : undefined
  };
};

const CalendarDayColumn = ({
  day,
  muted,
  timedItems,
  allDayItems,
  draggingKey,
  onSelectItem,
  onDragStart,
  onDragEnd,
  onDropTimed,
  onDropAllDay,
  onResizeItem
}: DayColumnProps) => {
  const [dragSection, setDragSection] = useState<'timed' | 'allDay' | null>(null);
  const resizingKeyRef = useRef<string | null>(null);
  const dayKey = toDayKey(day);

  useEffect(() => {
    if (!draggingKey) {
      setDragSection(null);
    }
  }, [draggingKey]);

  const sortedTimed = useMemo(() => sortItems(timedItems), [timedItems]);
  const sortedAllDay = useMemo(() => sortItems(allDayItems), [allDayItems]);
  const overlapKeys = useMemo(() => getOverlapKeys(sortedTimed), [sortedTimed]);

  const allDayOverflow = useOverflowIndicator({
    itemCount: sortedAllDay.length,
    itemHeight: ALL_DAY_CARD_HEIGHT,
    gap: ALL_DAY_CARD_GAP,
    trackScroll: false
  });
  const timedOverflow = useOverflowIndicator({
    itemCount: sortedTimed.length,
    itemHeight: TIMED_CARD_HEIGHT,
    gap: TIMED_CARD_GAP,
    trackScroll: true
  });

  const visibleAllDay = sortedAllDay.slice(0, allDayOverflow.visibleCount);
  const remainingAllDay = sortedAllDay.length - visibleAllDay.length;

  const handleDragStart = (event: DragEvent<HTMLDivElement>, item: CalendarItem) => {
    if (resizingKeyRef.current === item.key) {
      event.preventDefault();
      return;
    }
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', item.key);
    onDragStart(item);
  };

  const handleResizeStart = (event: PointerEvent<HTMLDivElement>, item: CalendarItem) => {
    if (!onResizeItem) return;
    event.preventDefault();
    event.stopPropagation();
    resizingKeyRef.current = item.key;
    const startY = event.clientY;
    const initialEnd = item.end;
    let deltaMinutes = 0;

    const handleMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientY - startY;
      const steps = Math.round(delta / RESIZE_STEP_PX);
      deltaMinutes = steps * RESIZE_STEP_MINUTES;
    };

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
      resizingKeyRef.current = null;
      if (!deltaMinutes) return;
      const proposedEnd = new Date(initialEnd.getTime() + deltaMinutes * 60000);
      const minEnd = new Date(item.start.getTime() + MIN_EVENT_DURATION_MINUTES * 60000);
      const finalEnd = proposedEnd < minEnd ? minEnd : proposedEnd;
      if (finalEnd.getTime() !== item.end.getTime()) {
        onResizeItem(item, item.start, finalEnd);
      }
    };

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
  };

  const handleDropTimed = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragSection(null);
    onDropTimed(day);
  };

  const handleDropAllDay = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragSection(null);
    onDropAllDay(day);
  };

  const handleSelect = (item: CalendarItem) => {
    if (draggingKey) return;
    onSelectItem?.(item);
  };

  return (
    <DayColumn $muted={muted} data-day={dayKey}>
      <DayHeader>
        <DayName>{formatDayName(day)}</DayName>
        <DayDate>{formatDayDate(day)}</DayDate>
      </DayHeader>

      <DropZone
        $active={dragSection === 'allDay'}
        onDragOver={(event) => {
          event.preventDefault();
          setDragSection('allDay');
        }}
        onDragLeave={() => setDragSection(null)}
        onDrop={handleDropAllDay}
      >
        <AllDaySection>
          <AllDayLabel>All day</AllDayLabel>
          <AllDayList ref={allDayOverflow.containerRef}>
            {visibleAllDay.map((item) => (
              <CardButton
                key={item.key}
                role="button"
                tabIndex={0}
                draggable
                onDragStart={(event) => handleDragStart(event, item)}
                onDragEnd={onDragEnd}
                onClick={() => handleSelect(item)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleSelect(item);
                  }
                }}
                $kind={item.kind}
                $allDay
                $stacked={false}
                $dragging={draggingKey === item.key}
              >
                <TimeRow>
                  <TimeBadge>All day</TimeBadge>
                </TimeRow>
                <CardTitle>{item.title}</CardTitle>
              </CardButton>
            ))}
          </AllDayList>
          {remainingAllDay > 0 ? <MoreIndicator>+{remainingAllDay} more</MoreIndicator> : null}
        </AllDaySection>
      </DropZone>

      <DropZone
        $active={dragSection === 'timed'}
        onDragOver={(event) => {
          event.preventDefault();
          setDragSection('timed');
        }}
        onDragLeave={() => setDragSection(null)}
        onDrop={handleDropTimed}
      >
        <TimedSection>
          <TimedList ref={timedOverflow.containerRef} onScroll={timedOverflow.onScroll}>
            {sortedTimed.map((item) => (
              <CardButton
                key={item.key}
                role="button"
                tabIndex={0}
                draggable
                onDragStart={(event) => handleDragStart(event, item)}
                onDragEnd={onDragEnd}
                onClick={() => handleSelect(item)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleSelect(item);
                  }
                }}
                $kind={item.kind}
                $allDay={false}
                $stacked={overlapKeys.has(item.key)}
                $dragging={draggingKey === item.key}
              >
                <TimeRow>
                  <TimeBadge>{getTimeLabel(item)}</TimeBadge>
                </TimeRow>
                <CardTitle>{item.title}</CardTitle>
                {item.kind === 'event' && onResizeItem ? (
                  <ResizeHandle
                    role="presentation"
                    onPointerDown={(event) => handleResizeStart(event, item)}
                  />
                ) : null}
              </CardButton>
            ))}
          </TimedList>
          {timedOverflow.remaining > 0 ? <MoreIndicator>+{timedOverflow.remaining} more</MoreIndicator> : null}
        </TimedSection>
      </DropZone>
    </DayColumn>
  );
};

export function CalendarWeekView({
  days,
  timedItems,
  allDayItems,
  mutedDayIndex,
  onSelectItem,
  onMoveItem,
  onResizeItem,
  onMoveAllDayItem
}: Props) {
  const [draggingItem, setDraggingItem] = useState<CalendarItem | null>(null);
  const [draggingKey, setDraggingKey] = useState<string | null>(null);

  const timedByDay = useMemo(() => groupItemsByDay(days, timedItems), [days, timedItems]);
  const allDayByDay = useMemo(() => groupItemsByDay(days, allDayItems), [days, allDayItems]);

  const handleDragStart = (item: CalendarItem) => {
    setDraggingItem(item);
    setDraggingKey(item.key);
  };

  const handleDragEnd = () => {
    setDraggingItem(null);
    setDraggingKey(null);
  };

  const handleDropTimed = (day: Date) => {
    if (!draggingItem || draggingItem.allDay || !onMoveItem) return;
    const { start, end } = shiftItemToDay(draggingItem, day);
    onMoveItem(draggingItem, start, end);
  };

  const handleDropAllDay = (day: Date) => {
    if (!draggingItem || !onMoveAllDayItem) return;
    onMoveAllDayItem(draggingItem, day);
  };

  return (
    <WeekGrid>
      {days.map((day, index) => {
        const key = toDayKey(day);
        return (
          <CalendarDayColumn
            key={key}
            day={day}
            muted={mutedDayIndex === index}
            timedItems={timedByDay.get(key) ?? []}
            allDayItems={allDayByDay.get(key) ?? []}
            draggingKey={draggingKey}
            onSelectItem={onSelectItem}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDropTimed={handleDropTimed}
            onDropAllDay={handleDropAllDay}
            onResizeItem={onResizeItem}
          />
        );
      })}
    </WeekGrid>
  );
}

const groupItemsByDay = (days: Date[], items: CalendarItem[]) => {
  const map = new Map<string, CalendarItem[]>();
  days.forEach((day) => map.set(toDayKey(day), []));
  items.forEach((item) => {
    const key = toDayKey(item.start);
    const bucket = map.get(key);
    if (bucket) bucket.push(item);
  });
  return map;
};

const sortItems = (items: CalendarItem[]) =>
  [...items].sort((left, right) => {
    const leftPriority = left.priority ?? 0;
    const rightPriority = right.priority ?? 0;
    if (leftPriority !== rightPriority) return leftPriority - rightPriority;
    const timeDelta = left.start.getTime() - right.start.getTime();
    if (timeDelta !== 0) return timeDelta;
    return left.title.localeCompare(right.title);
  });

const getOverlapKeys = (items: CalendarItem[]) => {
  const overlaps = new Set<string>();
  const events = items.filter((item) => item.kind === 'event');
  for (let i = 0; i < events.length; i += 1) {
    for (let j = i + 1; j < events.length; j += 1) {
      const left = events[i];
      const right = events[j];
      if (left.start < right.end && left.end > right.start) {
        overlaps.add(left.key);
        overlaps.add(right.key);
      }
    }
  }
  return overlaps;
};

const shiftItemToDay = (item: CalendarItem, day: Date) => {
  const durationMs = item.end.getTime() - item.start.getTime();
  const target = new Date(day);
  target.setHours(item.start.getHours(), item.start.getMinutes(), 0, 0);
  return {
    start: target,
    end: new Date(target.getTime() + durationMs)
  };
};

const formatDayName = (date: Date) =>
  date.toLocaleDateString(undefined, { weekday: 'short' });

const formatDayDate = (date: Date) =>
  date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

const formatTime = (date: Date) =>
  date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });

const getTimeLabel = (item: CalendarItem) => {
  if (item.kind === 'todo') {
    return formatTime(item.end);
  }
  if (isFullDayRange(item.start, item.end)) {
    return 'All day';
  }
  return formatTime(item.start);
};

const toDayKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const isFullDayRange = (start: Date, end: Date) =>
  start.getHours() === 0 &&
  start.getMinutes() === 0 &&
  end.getHours() === 23 &&
  end.getMinutes() === 59;

const hexToRgba = (hex: string, alpha: number) => {
  const sanitized = hex.replace('#', '');
  const parsed = sanitized.length === 3
    ? sanitized.split('').map((char) => char + char).join('')
    : sanitized;
  const int = parseInt(parsed, 16);
  const r = (int >> 16) & 255;
  const g = (int >> 8) & 255;
  const b = int & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};
