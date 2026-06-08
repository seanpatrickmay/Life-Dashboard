// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../../test/renderWithProviders';
import { CalendarDetailDrawer } from './CalendarDetailDrawer';
import type { CalendarItem } from './CalendarWeekView';
import type { CalendarEvent } from '../../services/api';

// ─── fixture helpers ────────────────────────────────────────────────────────

const makeEvent = (overrides: Partial<CalendarEvent> = {}): CalendarEvent => ({
  id: 42,
  calendar_google_id: 'primary',
  calendar_summary: 'Personal',
  calendar_primary: true,
  calendar_is_life_dashboard: false,
  google_event_id: 'evt-42',
  summary: 'Team standup',
  start_time: '2026-06-10T10:00:00.000Z',
  end_time: '2026-06-10T10:30:00.000Z',
  is_all_day: false,
  status: 'confirmed',
  ...overrides,
});

const makeItem = (event: CalendarEvent): CalendarItem => ({
  key: `event-${event.id}`,
  kind: 'event',
  title: event.summary ?? 'Event',
  start: new Date(event.start_time!),
  end: new Date(event.end_time!),
  allDay: event.is_all_day,
  data: event,
});

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  recurrenceScope: 'occurrence' as const,
  onChangeScope: vi.fn(),
  onReschedule: vi.fn(),
};

// ─── tests ───────────────────────────────────────────────────────────────────

describe('CalendarDetailDrawer — reschedule picker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  // ── closed state ─────────────────────────────────────────────────────────

  it('renders nothing meaningful when item is null', () => {
    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={null} />
    );
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
  });

  // ── timed event: Save calls onReschedule with updated start/end ──────────

  it('calls onReschedule with new date/time when Save is clicked (timed event)', () => {
    const event = makeEvent();
    const item = makeItem(event);
    const onReschedule = vi.fn();

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={onReschedule} />
    );

    // Change the date
    const dateInput = screen.getByLabelText(/date/i);
    fireEvent.change(dateInput, { target: { value: '2026-06-15' } });

    // Change start time
    const startInput = screen.getByLabelText(/start time/i);
    fireEvent.change(startInput, { target: { value: '09:00' } });

    // Change end time
    const endInput = screen.getByLabelText(/end time/i);
    fireEvent.change(endInput, { target: { value: '09:45' } });

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(onReschedule).toHaveBeenCalledTimes(1);
    const [calledItem, calledStart, calledEnd, calledIsAllDay] = onReschedule.mock.calls[0];
    expect(calledItem).toBe(item);
    expect(calledStart).toBeInstanceOf(Date);
    expect(calledEnd).toBeInstanceOf(Date);
    expect(calledIsAllDay).toBe(false);

    // Verify date parts — 2026-06-15 09:00 local
    expect(calledStart.getFullYear()).toBe(2026);
    expect(calledStart.getMonth()).toBe(5); // June = 5 (0-indexed)
    expect(calledStart.getDate()).toBe(15);
    expect(calledStart.getHours()).toBe(9);
    expect(calledStart.getMinutes()).toBe(0);

    // end: same date, 09:45
    expect(calledEnd.getFullYear()).toBe(2026);
    expect(calledEnd.getDate()).toBe(15);
    expect(calledEnd.getHours()).toBe(9);
    expect(calledEnd.getMinutes()).toBe(45);
  });

  // ── Cancel/close does NOT call onReschedule ───────────────────────────────

  it('does NOT call onReschedule when Cancel is clicked', () => {
    const event = makeEvent();
    const item = makeItem(event);
    const onReschedule = vi.fn();

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={onReschedule} />
    );

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onReschedule).not.toHaveBeenCalled();
  });

  it('does NOT call onReschedule when the Close (drawer) button is clicked', () => {
    const event = makeEvent();
    const item = makeItem(event);
    const onClose = vi.fn();
    const onReschedule = vi.fn();

    renderWithProviders(
      <CalendarDetailDrawer
        {...defaultProps}
        item={item}
        onClose={onClose}
        onReschedule={onReschedule}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /^close details$/i }));
    expect(onReschedule).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  // ── All-day event: no time inputs; Save passes isAllDay=true ─────────────

  it('shows only a date input (no time) for all-day events', () => {
    const event = makeEvent({ is_all_day: true, start_time: '2026-06-10T00:00:00.000Z', end_time: '2026-06-11T00:00:00.000Z' });
    const item = makeItem(event);

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={vi.fn()} />
    );

    expect(screen.queryByLabelText(/start time/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/end time/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/date/i)).toBeInTheDocument();
  });

  it('calls onReschedule with isAllDay=true for all-day events', () => {
    const event = makeEvent({
      is_all_day: true,
      start_time: '2026-06-10T00:00:00.000Z',
      end_time: '2026-06-11T00:00:00.000Z',
    });
    const item = makeItem(event);
    const onReschedule = vi.fn();

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={onReschedule} />
    );

    const dateInput = screen.getByLabelText(/date/i);
    fireEvent.change(dateInput, { target: { value: '2026-06-20' } });

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(onReschedule).toHaveBeenCalledTimes(1);
    const [, , , calledIsAllDay] = onReschedule.mock.calls[0];
    expect(calledIsAllDay).toBe(true);
  });

  // ── Recurring events: scope selector is visible and active ───────────────

  it('shows the scope selector for recurring events', () => {
    const event = makeEvent({ recurring_event_id: 'rrule-abc' });
    const item = makeItem(event);

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={vi.fn()} />
    );

    expect(screen.getByRole('button', { name: /this event/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /this & future/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /entire series/i })).toBeInTheDocument();
  });

  it('calls onChangeScope when a scope button is clicked', () => {
    const event = makeEvent({ recurring_event_id: 'rrule-abc' });
    const item = makeItem(event);
    const onChangeScope = vi.fn();

    renderWithProviders(
      <CalendarDetailDrawer
        {...defaultProps}
        item={item}
        onChangeScope={onChangeScope}
        onReschedule={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /this & future/i }));
    expect(onChangeScope).toHaveBeenCalledWith('future');
  });

  // ── Guest mode: Save button is disabled ──────────────────────────────────

  it('disables the Save button in guest mode', () => {
    localStorage.setItem('ld_guest_mode', '1');

    const event = makeEvent();
    const item = makeItem(event);

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={vi.fn()} />
    );

    const saveBtn = screen.getByRole('button', { name: /save/i });
    expect(saveBtn).toBeDisabled();
  });

  // ── Inputs are seeded from the event's current start/end ─────────────────

  it('seeds the date input from the event start time', () => {
    // start_time: 2026-06-10T14:30:00.000Z → local date depends on TZ, but
    // we can check that the date input has a populated value
    const event = makeEvent({ start_time: '2026-06-10T14:30:00.000Z', end_time: '2026-06-10T15:00:00.000Z' });
    const item = makeItem(event);

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={vi.fn()} />
    );

    const dateInput = screen.getByLabelText(/date/i) as HTMLInputElement;
    expect(dateInput.value).not.toBe('');
  });

  // ── End-before-start validation (timed events only) ──────────────────────

  it('disables Save and does NOT call onReschedule when end time is before start time', () => {
    const event = makeEvent({
      start_time: '2026-06-10T10:00:00.000Z',
      end_time: '2026-06-10T10:30:00.000Z',
    });
    const item = makeItem(event);
    const onReschedule = vi.fn();

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={item} onReschedule={onReschedule} />
    );

    // Set start to 09:00 and end to 08:00 (end before start)
    fireEvent.change(screen.getByLabelText(/start time/i), { target: { value: '09:00' } });
    fireEvent.change(screen.getByLabelText(/end time/i), { target: { value: '08:00' } });

    const saveBtn = screen.getByRole('button', { name: /save/i });
    expect(saveBtn).toBeDisabled();

    fireEvent.click(saveBtn);
    expect(onReschedule).not.toHaveBeenCalled();
  });

  // ── No reschedule form for todos ─────────────────────────────────────────

  it('does not render the reschedule form for todo items', () => {
    const todoItem: CalendarItem = {
      key: 'todo-1',
      kind: 'todo',
      title: 'Buy groceries',
      start: new Date(),
      end: new Date(),
      allDay: false,
      data: {
        id: 1,
        project_id: 0,
        text: 'Buy groceries',
        completed: false,
        deadline_utc: null,
        deadline_is_date_only: false,
        time_horizon: 'this_week',
        is_overdue: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    };

    renderWithProviders(
      <CalendarDetailDrawer {...defaultProps} item={todoItem} onReschedule={vi.fn()} />
    );

    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
  });
});
