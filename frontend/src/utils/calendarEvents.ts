import type { CalendarEvent } from '../services/api';

/**
 * Returns the YYYY-MM-DD local date string for a given Date object.
 * Used for comparing calendar event dates to a target day without
 * timezone skew from ISO string parsing.
 */
const toLocalDateStr = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

/**
 * Returns true if the given CalendarEvent falls on the given local day.
 *
 * - Timed events: compared using local Y/M/D of start_time.
 * - All-day events: compared using the UTC date strings stored in start_time
 *   and end_time.  Google Calendar stores all-day end dates as exclusive
 *   (i.e., the day AFTER the last day).  An event is on `day` when:
 *     startDateStr <= dayStr < endDateStr
 *   This matches how Calendar.tsx's splitEventSegments iterates segments.
 *
 * Events with null start_time are excluded (no usable date).
 */
export function isEventOnLocalDay(event: CalendarEvent, day: Date): boolean {
  if (!event.start_time) return false;

  if (event.is_all_day) {
    // All-day events: use UTC date portion of the stored ISO strings.
    // The backend stores midnight-UTC of the local date, so the UTC date
    // component is the canonical date for the all-day event.
    const startDate = new Date(event.start_time);
    const startDateStr = startDate.toISOString().slice(0, 10); // YYYY-MM-DD UTC

    const dayStr = toLocalDateStr(day);

    if (!event.end_time) {
      // No end_time: treat as single-day event
      return startDateStr === dayStr;
    }

    const endDate = new Date(event.end_time);
    const endDateStr = endDate.toISOString().slice(0, 10); // exclusive end

    // Event spans day if: startDateStr <= dayStr < endDateStr
    return startDateStr <= dayStr && dayStr < endDateStr;
  }

  // Timed event: compare using local Y/M/D so 11:59 PM events
  // on today still count even across DST.
  const start = new Date(event.start_time);
  return toLocalDateStr(start) === toLocalDateStr(day);
}
