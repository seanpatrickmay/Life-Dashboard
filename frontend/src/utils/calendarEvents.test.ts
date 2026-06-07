import { describe, expect, it } from 'vitest';
import { isEventOnLocalDay } from './calendarEvents';
import type { CalendarEvent } from '../services/api';

// Minimal CalendarEvent factory — only the fields the predicate cares about.
const makeEvent = (overrides: Partial<CalendarEvent>): CalendarEvent => ({
  id: 1,
  calendar_google_id: 'test',
  calendar_summary: 'Test',
  calendar_primary: true,
  calendar_is_life_dashboard: false,
  google_event_id: 'test-1',
  start_time: null,
  end_time: null,
  is_all_day: false,
  ...overrides,
});

// Build a local midnight date string in the format the backend emits for
// all-day events: midnight UTC on the given local date.  We rely on the fact
// that the predicate must handle the UTC-midnight representation correctly
// regardless of the test runner's local timezone by using date-string
// comparison instead of local Date arithmetic.
const toMidnightUTC = (localDateStr: string) =>
  new Date(localDateStr + 'T00:00:00.000Z').toISOString();

describe('isEventOnLocalDay', () => {
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;

  // ── Timed events ────────────────────────────────────────────────────────────

  it('returns true for a timed event that starts today', () => {
    const event = makeEvent({
      is_all_day: false,
      start_time: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 10, 0).toISOString(),
      end_time: new Date(today.getFullYear(), today.getMonth(), today.getDate(), 11, 0).toISOString(),
    });
    expect(isEventOnLocalDay(event, today)).toBe(true);
  });

  it('returns false for a timed event that starts tomorrow', () => {
    const event = makeEvent({
      is_all_day: false,
      start_time: new Date(tomorrow.getFullYear(), tomorrow.getMonth(), tomorrow.getDate(), 10, 0).toISOString(),
      end_time: new Date(tomorrow.getFullYear(), tomorrow.getMonth(), tomorrow.getDate(), 11, 0).toISOString(),
    });
    expect(isEventOnLocalDay(event, today)).toBe(false);
  });

  it('returns false for a timed event that started yesterday', () => {
    const event = makeEvent({
      is_all_day: false,
      start_time: new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate(), 10, 0).toISOString(),
      end_time: new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate(), 11, 0).toISOString(),
    });
    expect(isEventOnLocalDay(event, today)).toBe(false);
  });

  it('returns false for a timed event with no start_time', () => {
    const event = makeEvent({ is_all_day: false, start_time: null });
    expect(isEventOnLocalDay(event, today)).toBe(false);
  });

  // ── All-day events — the bug cases ──────────────────────────────────────────

  it('returns true for an all-day event on today (the key bug case)', () => {
    // All-day event: start = today midnight UTC, end = tomorrow midnight UTC (exclusive)
    const event = makeEvent({
      is_all_day: true,
      start_time: toMidnightUTC(todayStr),
      end_time: toMidnightUTC(tomorrowStr),
    });
    expect(isEventOnLocalDay(event, today)).toBe(true);
  });

  it('returns false for an all-day event that is tomorrow (not today)', () => {
    const dayAfterTomorrow = new Date(tomorrow);
    dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 1);
    const dayAfterTomorrowStr = `${dayAfterTomorrow.getFullYear()}-${String(dayAfterTomorrow.getMonth() + 1).padStart(2, '0')}-${String(dayAfterTomorrow.getDate()).padStart(2, '0')}`;

    const event = makeEvent({
      is_all_day: true,
      start_time: toMidnightUTC(tomorrowStr),
      end_time: toMidnightUTC(dayAfterTomorrowStr),
    });
    expect(isEventOnLocalDay(event, today)).toBe(false);
  });

  it('returns false for an all-day event that ended yesterday (exclusive end)', () => {
    // start = yesterday, end = today — exclusive end means it does NOT cover today
    const event = makeEvent({
      is_all_day: true,
      start_time: toMidnightUTC(yesterdayStr),
      end_time: toMidnightUTC(todayStr),
    });
    expect(isEventOnLocalDay(event, today)).toBe(false);
  });

  it('returns true for a multi-day all-day event that spans today', () => {
    const dayAfterTomorrow = new Date(tomorrow);
    dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 1);
    const dayAfterTomorrowStr = `${dayAfterTomorrow.getFullYear()}-${String(dayAfterTomorrow.getMonth() + 1).padStart(2, '0')}-${String(dayAfterTomorrow.getDate()).padStart(2, '0')}`;

    // start = yesterday, end = day after tomorrow → covers yesterday, today, tomorrow
    const event = makeEvent({
      is_all_day: true,
      start_time: toMidnightUTC(yesterdayStr),
      end_time: toMidnightUTC(dayAfterTomorrowStr),
    });
    expect(isEventOnLocalDay(event, today)).toBe(true);
  });

  it('returns false for an all-day event with no start_time', () => {
    const event = makeEvent({ is_all_day: true, start_time: null, end_time: null });
    expect(isEventOnLocalDay(event, today)).toBe(false);
  });
});
