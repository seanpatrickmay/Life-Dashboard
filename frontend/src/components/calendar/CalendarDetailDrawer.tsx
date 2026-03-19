import { useEffect, useMemo } from 'react';
import styled, { css } from 'styled-components';
import { composeLayers, getCardLayers } from '../../theme/monetTheme';
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

const Panel = styled.div<{ $open: boolean }>`
  display: grid;
  grid-template-rows: ${({ $open }) => ($open ? '1fr' : '0fr')};
  transition: grid-template-rows 0.3s ease;

  @media (prefers-reduced-motion: reduce) {
    transition-duration: 0.01ms;
  }
`;

const PanelInner = styled.div`
  overflow: hidden;
`;

const PanelCard = styled.div`
  position: relative;
  border-radius: 24px;
  padding: clamp(18px, 2vw, 28px);
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  box-shadow: ${({ theme }) => theme.shadows.soft};
  display: flex;
  flex-direction: column;
  gap: 18px;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 24px;
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

const PanelContent = styled.div`
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 32px;

  @media (max-width: 700px) {
    grid-template-columns: 1fr;
  }
`;

const HeaderRow = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  grid-column: 1 / -1;
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
  flex-shrink: 0;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Section = styled.section`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const FullWidthSection = styled(Section)`
  grid-column: 1 / -1;
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
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const ScrollSection = styled.div`
  padding-right: 4px;
  overflow: auto;
  max-height: 180px;
  border-radius: 12px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.surfaceInset};
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
    $active ? theme.colors.overlayActive : 'transparent'};
  color: ${({ theme }) => theme.colors.textPrimary};

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const MeetingLink = styled.a`
  font-size: 0.85rem;
  color: ${({ theme }) => theme.palette?.pond?.['200'] ?? theme.colors.accent};
  text-decoration: none;
  word-break: break-all;

  &:hover {
    text-decoration: underline;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

export function CalendarDetailDrawer({
  open,
  item,
  onClose,
  recurrenceScope,
  onChangeScope
}: Props) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

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
    <Panel $open={open}>
      <PanelInner>
        <PanelCard role="region" aria-label="Event details">
          <PanelContent>
            <HeaderRow>
              <Title>{item?.title ?? 'Details'}</Title>
              <CloseButton type="button" onClick={onClose} aria-label="Close details">
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

                <Section>
                  <Label>Status</Label>
                  <BadgeRow>
                    {event.recurring_event_id ? <Badge>Recurring</Badge> : null}
                    {event.visibility ? <Badge>{event.visibility}</Badge> : null}
                    <Badge>{busyLabel}</Badge>
                  </BadgeRow>
                </Section>

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
                    <MeetingLink
                      href={event.conference_link ?? event.hangout_link ?? '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Join meeting
                    </MeetingLink>
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

                {event.description ? (
                  <FullWidthSection>
                    <Label>Description</Label>
                    <ScrollSection>
                      <DescriptionText>{event.description}</DescriptionText>
                    </ScrollSection>
                  </FullWidthSection>
                ) : null}
              </>
            ) : (
              <Section>
                <Label>Todo</Label>
                <Value>{todo?.text ?? 'No details available.'}</Value>
              </Section>
            )}
          </PanelContent>
        </PanelCard>
      </PanelInner>
    </Panel>
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
