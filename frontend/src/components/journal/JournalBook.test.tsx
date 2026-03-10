// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'styled-components';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const useJournalMock = vi.fn();
const useCalendarEventsMock = vi.fn();
const fetchJournalDayMock = vi.fn();

vi.mock('../../hooks/useJournal', () => ({
  useJournal: (...args: unknown[]) => useJournalMock(...args)
}));

vi.mock('../../hooks/useCalendar', () => ({
  useCalendarEvents: (...args: unknown[]) => useCalendarEventsMock(...args)
}));

vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof import('../../services/api')>('../../services/api');
  return {
    ...actual,
    fetchJournalDay: (...args: unknown[]) => fetchJournalDayMock(...args)
  };
});

import { JournalBook } from './JournalBook';

const theme = {
  fonts: { heading: 'sans-serif', body: 'sans-serif' },
  mode: 'dark',
  palette: {
    neutral: {
      '50': '#fafafa',
      '200': '#e5e5e5',
      '700': '#525252',
      '900': '#171717'
    }
  }
};

const todayKey = '2026-03-10';
const priorDayKey = '2026-03-09';

const todayResponse = {
  local_date: todayKey,
  time_zone: 'America/New_York',
  status: 'open',
  entries: [],
  completed_items: [
    {
      id: 11,
      text: 'Uploaded the reimbursement PDF',
      completed_at_utc: '2026-03-10T14:15:00-04:00'
    }
  ],
  summary: null
};

const priorDayResponse = {
  local_date: priorDayKey,
  time_zone: 'America/New_York',
  status: 'final',
  entries: [],
  completed_items: [],
  summary: {
    groups: [
      {
        title: 'Admin',
        items: [
          {
            text: 'Uploaded the reimbursement PDF',
            time_label: '2:15 PM',
            occurred_at_local: '2026-03-09T14:15:00-04:00',
            time_precision: 'exact' as const
          }
        ]
      }
    ]
  }
};

const weekResponse = {
  week_start: '2026-03-09',
  week_end: '2026-03-15',
  days: [
    { local_date: priorDayKey, has_entries: false, has_summary: true, completed_count: 1 },
    { local_date: todayKey, has_entries: true, has_summary: false, completed_count: 1 },
    { local_date: '2026-03-11', has_entries: false, has_summary: false, completed_count: 0 },
    { local_date: '2026-03-12', has_entries: false, has_summary: false, completed_count: 0 },
    { local_date: '2026-03-13', has_entries: false, has_summary: false, completed_count: 0 },
    { local_date: '2026-03-14', has_entries: false, has_summary: false, completed_count: 0 },
    { local_date: '2026-03-15', has_entries: false, has_summary: false, completed_count: 0 }
  ]
};

function renderJournalBook() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <JournalBook />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

describe('JournalBook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-10T15:00:00-04:00'));
    useJournalMock.mockReset();
    useCalendarEventsMock.mockReset();
    fetchJournalDayMock.mockReset();
    useCalendarEventsMock.mockReturnValue({
      eventsQuery: {
        data: { events: [] },
        isLoading: false
      },
      syncCalendar: vi.fn(),
      updateCalendarEvent: vi.fn(),
      isSyncing: false
    });
    fetchJournalDayMock.mockResolvedValue(todayResponse);
    useJournalMock.mockImplementation((selectedDate: string) => ({
      timeZone: 'America/New_York',
      dayQuery: {
        data: selectedDate === todayKey ? todayResponse : priorDayResponse,
        isLoading: false,
        error: null
      },
      weekQuery: {
        data: weekResponse
      },
      createEntry: vi.fn(),
      isSavingEntry: false
    }));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders current-day completed item timestamps', () => {
    const timeSpy = vi.spyOn(Date.prototype, 'toLocaleTimeString').mockReturnValue('2:15 PM');

    renderJournalBook();

    expect(screen.getAllByText('2:15 PM').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Uploaded the reimbursement PDF').length).toBeGreaterThan(0);

    timeSpy.mockRestore();
  });

  it('renders timestamped past-day summary items', () => {
    renderJournalBook();

    fireEvent.click(screen.getByLabelText('Previous day'));

    expect(screen.getByText('2:15 PM')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getAllByText('Uploaded the reimbursement PDF').length).toBeGreaterThan(0);
  });
});
