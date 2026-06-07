import { useEffect, useMemo, useState } from 'react';
import styled from 'styled-components';
import { isGuestMode } from '../../demo/guest/guestMode';
import type { CalendarEvent } from '../../services/api';
import type { CalendarItem } from './CalendarWeekView';

// ─── Props ────────────────────────────────────────────────────────────────────

type Props = {
  item: CalendarItem;
  onReschedule: (item: CalendarItem, start: Date, end: Date, isAllDay: boolean) => Promise<void> | void;
};

// ─── Styled components ────────────────────────────────────────────────────────

const Section = styled.section`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const RescheduleSection = styled(Section)`
  grid-column: 1 / -1;
  border-top: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  padding-top: 14px;
  margin-top: 4px;
`;

const RescheduleFieldRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
`;

const FieldGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 120px;
`;

const FieldLabel = styled.label`
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const FieldInput = styled.input`
  background: ${({ theme }) => theme.colors.surfaceInset};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 0.82rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.body};
  outline: none;
  width: 100%;
  box-sizing: border-box;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }

  /* Colour-scheme so date/time pickers respect the active theme mode */
  color-scheme: ${({ theme }) => (theme.mode === 'dark' ? 'dark' : 'light')};
`;

const RescheduleButtonRow = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 4px;
`;

const SaveButton = styled.button`
  border-radius: 999px;
  padding: 7px 16px;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-family: ${({ theme }) => theme.fonts.heading};
  cursor: pointer;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlayActive};
  color: ${({ theme }) => theme.colors.textPrimary};
  transition: opacity 0.15s ease;

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  &:not(:disabled):hover {
    opacity: 0.85;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const CancelButton = styled.button`
  border-radius: 999px;
  padding: 7px 16px;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-family: ${({ theme }) => theme.fonts.heading};
  cursor: pointer;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: transparent;
  color: ${({ theme }) => theme.colors.textSecondary};
  transition: color 0.15s ease;

  &:hover {
    color: ${({ theme }) => theme.colors.textPrimary};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const GuestNotice = styled.span`
  font-size: 0.72rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  letter-spacing: 0.06em;
`;

const FormLabel = styled.span`
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Format a Date as YYYY-MM-DD for <input type="date"> */
export const toDateValue = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

/** Format a Date as HH:MM for <input type="time"> */
export const toTimeValue = (d: Date): string => {
  const h = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${min}`;
};

/** Build a local Date from a YYYY-MM-DD string and an HH:MM string. */
export const buildDateTime = (dateStr: string, timeStr: string): Date => {
  const [year, month, day] = dateStr.split('-').map(Number);
  const [hours, minutes] = timeStr.split(':').map(Number);
  return new Date(year, month - 1, day, hours, minutes, 0, 0);
};

// ─── Component ────────────────────────────────────────────────────────────────

export function RescheduleForm({ item, onReschedule }: Props) {
  const event = item.kind === 'event' ? (item.data as CalendarEvent) : null;

  const initialDate = useMemo(() => {
    if (!event?.start_time) return '';
    return toDateValue(new Date(event.start_time));
  }, [event?.start_time]);

  const initialStartTime = useMemo(() => {
    if (!event?.start_time) return '';
    return toTimeValue(new Date(event.start_time));
  }, [event?.start_time]);

  const initialEndTime = useMemo(() => {
    if (!event?.end_time) return '';
    return toTimeValue(new Date(event.end_time));
  }, [event?.end_time]);

  const [dateValue, setDateValue] = useState(initialDate);
  const [startTimeValue, setStartTimeValue] = useState(initialStartTime);
  const [endTimeValue, setEndTimeValue] = useState(initialEndTime);
  const [isSaving, setIsSaving] = useState(false);

  // Re-seed when the selected event changes
  useEffect(() => {
    setDateValue(initialDate);
    setStartTimeValue(initialStartTime);
    setEndTimeValue(initialEndTime);
  }, [initialDate, initialStartTime, initialEndTime]);

  const guestMode = isGuestMode();

  const timedEndBeforeStart = useMemo(() => {
    if (event?.is_all_day || !dateValue || !startTimeValue || !endTimeValue) return false;
    const start = buildDateTime(dateValue, startTimeValue);
    const end = buildDateTime(dateValue, endTimeValue);
    return end <= start;
  }, [event?.is_all_day, dateValue, startTimeValue, endTimeValue]);

  const handleSave = async () => {
    if (!onReschedule || !dateValue) return;
    setIsSaving(true);
    try {
      if (event?.is_all_day) {
        const [year, month, day] = dateValue.split('-').map(Number);
        const start = new Date(year, month - 1, day, 0, 0, 0, 0);
        const end = new Date(year, month - 1, day + 1, 0, 0, 0, 0);
        await onReschedule(item, start, end, true);
      } else {
        const start = buildDateTime(dateValue, startTimeValue);
        const end = buildDateTime(dateValue, endTimeValue);
        if (end <= start) return;
        await onReschedule(item, start, end, false);
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setDateValue(initialDate);
    setStartTimeValue(initialStartTime);
    setEndTimeValue(initialEndTime);
  };

  return (
    <RescheduleSection aria-label="Reschedule event">
      <FormLabel>Reschedule</FormLabel>
      <RescheduleFieldRow>
        <FieldGroup>
          <FieldLabel htmlFor="reschedule-date">Date</FieldLabel>
          <FieldInput
            id="reschedule-date"
            type="date"
            value={dateValue}
            onChange={(e) => setDateValue(e.target.value)}
            aria-label="Date"
          />
        </FieldGroup>

        {!event?.is_all_day ? (
          <>
            <FieldGroup>
              <FieldLabel htmlFor="reschedule-start">Start time</FieldLabel>
              <FieldInput
                id="reschedule-start"
                type="time"
                value={startTimeValue}
                onChange={(e) => setStartTimeValue(e.target.value)}
                aria-label="Start time"
              />
            </FieldGroup>
            <FieldGroup>
              <FieldLabel htmlFor="reschedule-end">End time</FieldLabel>
              <FieldInput
                id="reschedule-end"
                type="time"
                value={endTimeValue}
                onChange={(e) => setEndTimeValue(e.target.value)}
                aria-label="End time"
              />
            </FieldGroup>
          </>
        ) : null}
      </RescheduleFieldRow>

      <RescheduleButtonRow>
        <SaveButton
          type="button"
          onClick={handleSave}
          disabled={guestMode || isSaving || !dateValue || timedEndBeforeStart}
          aria-label="Save reschedule"
          aria-busy={isSaving}
        >
          {isSaving ? 'Saving…' : 'Save'}
        </SaveButton>
        <CancelButton
          type="button"
          onClick={handleCancel}
          aria-label="Cancel reschedule"
        >
          Cancel
        </CancelButton>
        {guestMode ? (
          <GuestNotice>Editing unavailable in demo mode.</GuestNotice>
        ) : timedEndBeforeStart ? (
          <GuestNotice>End time must be after start time.</GuestNotice>
        ) : null}
      </RescheduleButtonRow>
    </RescheduleSection>
  );
}
