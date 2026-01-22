import { useMemo } from 'react';
import styled, { css } from 'styled-components';
import { composeLayers, getCardLayers } from '../../theme/monetTheme';
import { Z_LAYERS } from '../../styles/zLayers';
import type { CalendarEvent, TodoItem } from '../../services/api';
import type { CalendarItem } from './CalendarWeekView';

type RecurrenceScope = 'occurrence' | 'future' | 'series';

type Props = {
  open: boolean;
  item: CalendarItem | null;
  onClose: () => void;
  recurrenceScope: RecurrenceScope;
  onChangeScope?: (scope: RecurrenceScope) => void;
};

const Backdrop = styled.div<{ $open: boolean }>`
  position: fixed;
  inset: 0;
  background: ${({ theme }) => hexToRgba(theme.colors.textPrimary, 0.2)};
  opacity: ${({ $open }) => ($open ? 1 : 0)};
  pointer-events: ${({ $open }) => ($open ? 'auto' : 'none')};
  transition: opacity 0.2s ease;
  z-index: ${Z_LAYERS.overlays};
`;

const Drawer = styled.aside<{ $open: boolean }>`
  position: fixed;
  top: 0;
  right: 0;
  height: 100vh;
  width: min(420px, 92vw);
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 28px 24px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  border-left: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  box-shadow: 0 18px 42px ${({ theme }) => hexToRgba(theme.colors.textPrimary, 0.18)};
  transform: translateX(${({ $open }) => ($open ? '0' : '100%')});
  transition: transform 0.28s ease;
  z-index: ${Z_LAYERS.overlays + 1};
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.5;
    ${({ theme }) => {
      const layers = composeLayers(getCardLayers(theme.mode ?? 'light', theme.intensity ?? 'rich'));
      return css`
        background-image: ${layers.image};
        background-size: ${layers.size};
        background-repeat: ${layers.repeat};
        background-position: ${layers.position};
        mix-blend-mode: ${layers.blend ?? 'normal'};
      `;
    }}
  }
`;

const DrawerContent = styled.div`
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100%;
  overflow: hidden;
`;

const HeaderRow = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
`;

const Title = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-size: 0.9rem;
`;

const CloseButton = styled.button`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  border-radius: 999px;
  padding: 6px 12px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-size: 0.7rem;
  cursor: pointer;
`;

const Section = styled.section`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const Label = styled.span`
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const Value = styled.span`
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const BadgeRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const Badge = styled.span`
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.7rem;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => hexToRgba(theme.colors.textPrimary, 0.06)};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ScrollSection = styled.div`
  padding-right: 4px;
  overflow: auto;
  max-height: 240px;
  border-radius: 12px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => hexToRgba(theme.colors.textPrimary, 0.04)};
`;

const DescriptionText = styled.p`
  margin: 0;
  padding: 12px 14px;
  font-size: 0.82rem;
  line-height: 1.45;
  color: ${({ theme }) => theme.colors.textPrimary};
  white-space: pre-wrap;
`;

const AttendeeList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const AttendeeRow = styled.li`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.8rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const AttendeeStatus = styled.span`
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const ScopeRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const ScopeButton = styled.button<{ $active: boolean }>`
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  cursor: pointer;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme, $active }) =>
    $active ? hexToRgba(theme.colors.textPrimary, 0.14) : 'transparent'};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

export function CalendarDetailDrawer({
  open,
  item,
  onClose,
  recurrenceScope,
  onChangeScope
}: Props) {
  const payload = item?.data as CalendarEvent | TodoItem | undefined;
  const isEvent = item?.kind === 'event';
  const event = isEvent ? (payload as CalendarEvent) : null;
  const todo = !isEvent ? (payload as TodoItem) : null;

  const timeLabel = useMemo(() => {
    if (isEvent && event?.start_time && event?.end_time) {
      const start = new Date(event.start_time);
      const end = new Date(event.end_time);
      if (event.is_all_day) {
        const inclusiveEnd = new Date(end);
        inclusiveEnd.setDate(inclusiveEnd.getDate() - 1);
        if (isSameDay(start, inclusiveEnd)) {
          return `All day • ${formatDate(start)}`;
        }
        return `All day • ${formatDate(start)} – ${formatDate(inclusiveEnd)}`;
      }
      return `${formatDate(start)} • ${formatTime(start)} – ${formatTime(end)}`;
    }
    if (!isEvent && todo?.deadline_utc) {
      const deadline = new Date(todo.deadline_utc);
      if (todo.deadline_is_date_only) {
        return `Due • ${formatDate(deadline)} (all day)`;
      }
      return `Due • ${formatDate(deadline)} • ${formatTime(deadline)}`;
    }
    return 'No scheduled time';
  }, [event, todo, isEvent]);

  const attendeeList = useMemo(() => {
    if (!event?.attendees) return [];
    return event.attendees.map((attendee, index) => ({
      key: String(attendee.email ?? attendee.id ?? attendee.displayName ?? `attendee-${index}`),
      label: String(attendee.displayName ?? attendee.email ?? 'Guest'),
      status: String(attendee.responseStatus ?? 'needsAction')
    }));
  }, [event?.attendees]);

  const busyLabel = event?.transparency === 'transparent' ? 'Free' : 'Busy';

  return (
    <>
      <Backdrop $open={open} onClick={onClose} />
      <Drawer $open={open} role="dialog" aria-hidden={!open}>
        <DrawerContent>
          <HeaderRow>
            <Title>{item?.title ?? 'Details'}</Title>
            <CloseButton type="button" onClick={onClose}>
              Close
            </CloseButton>
          </HeaderRow>

          <Section>
            <Label>When</Label>
            <Value>{timeLabel}</Value>
          </Section>

          {event ? (
            <>
              <Section>
                <Label>Calendar</Label>
                <Value>{event.calendar_summary}</Value>
              </Section>
              <BadgeRow>
                {event.recurring_event_id ? <Badge>Recurring</Badge> : null}
                {event.visibility ? <Badge>{event.visibility}</Badge> : null}
                <Badge>{busyLabel}</Badge>
              </BadgeRow>
              {event.recurring_event_id && onChangeScope ? (
                <Section>
                  <Label>Edit scope</Label>
                  <ScopeRow>
                    {(['occurrence', 'future', 'series'] as RecurrenceScope[]).map((scope) => (
                      <ScopeButton
                        key={scope}
                        $active={recurrenceScope === scope}
                        type="button"
                        onClick={() => onChangeScope(scope)}
                      >
                        {scope === 'occurrence'
                          ? 'This event'
                          : scope === 'future'
                            ? 'This & future'
                            : 'Entire series'}
                      </ScopeButton>
                    ))}
                  </ScopeRow>
                </Section>
              ) : null}
              {event.location ? (
                <Section>
                  <Label>Location</Label>
                  <Value>{event.location}</Value>
                </Section>
              ) : null}
              {event.conference_link || event.hangout_link ? (
                <Section>
                  <Label>Meeting link</Label>
                  <Value>{event.conference_link ?? event.hangout_link}</Value>
                </Section>
              ) : null}
              {attendeeList.length ? (
                <Section>
                  <Label>Attendees</Label>
                  <AttendeeList>
                    {attendeeList.map((attendee) => (
                      <AttendeeRow key={attendee.key}>
                        <span>{attendee.label}</span>
                        <AttendeeStatus>{attendee.status}</AttendeeStatus>
                      </AttendeeRow>
                    ))}
                  </AttendeeList>
                </Section>
              ) : null}
              <Section>
                <Label>Description</Label>
                <ScrollSection>
                  <DescriptionText>{event.description || 'No description available.'}</DescriptionText>
                </ScrollSection>
              </Section>
            </>
          ) : (
            <Section>
              <Label>Todo</Label>
              <Value>{todo?.text ?? 'No details available.'}</Value>
            </Section>
          )}
        </DrawerContent>
      </Drawer>
    </>
  );
}

const formatDate = (value: Date) =>
  value.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });

const formatTime = (value: Date) =>
  value.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false });

const isSameDay = (left: Date, right: Date) =>
  left.getFullYear() === right.getFullYear() &&
  left.getMonth() === right.getMonth() &&
  left.getDate() === right.getDate();

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
