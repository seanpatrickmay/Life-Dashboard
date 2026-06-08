// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';
import { renderWithProviders } from '../test/renderWithProviders';

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock('../hooks/useJournal', () => ({
  useJournal: () => ({
    dayQuery: { isLoading: false, data: null, error: null },
    weekQuery: { isLoading: false, data: { days: [] } },
    createEntry: vi.fn(),
    isSavingEntry: false,
    timeZone: 'America/New_York',
  }),
}));

vi.mock('../hooks/useCalendar', () => ({
  useCalendarEvents: () => ({
    eventsQuery: { isLoading: false, data: { events: [] } },
  }),
}));

vi.mock('../services/api', () => ({
  fetchJournalDay: vi.fn().mockResolvedValue(null),
  fetchJournalWeek: vi.fn().mockResolvedValue({ days: [] }),
  createJournalEntry: vi.fn().mockResolvedValue({}),
}));

// Control savedToday helpers via a mock
const mockGetSavedTodayCount = vi.fn();

vi.mock('../services/savedToday', () => ({
  getSavedTodayCount: () => mockGetSavedTodayCount(),
  recordSavedToday: vi.fn(),
  getTodayLocalDate: () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  },
}));

// ── Constants ────────────────────────────────────────────────────────────

const DISMISSED_KEY = 'news.savedTodayPromptDismissed';

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ── Import component after mocks ─────────────────────────────────────────

import { ReflectPage } from './Reflect';

// ── Tests ────────────────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  mockGetSavedTodayCount.mockReturnValue(0);
});

afterEach(() => {
  localStorage.clear();
});

describe('Reflect saved-today nudge prompt', () => {
  it('shows no prompt when saved count is 0', () => {
    mockGetSavedTodayCount.mockReturnValue(0);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.queryByText(/saved/i)).toBeNull();
  });

  it('shows prompt with correct singular copy when 1 article saved', () => {
    mockGetSavedTodayCount.mockReturnValue(1);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/You saved 1 read today/i)).toBeInTheDocument();
  });

  it('shows prompt with correct plural copy when 3 articles saved', () => {
    mockGetSavedTodayCount.mockReturnValue(3);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/You saved 3 reads today/i)).toBeInTheDocument();
  });

  it('dismiss button has accessible label', () => {
    mockGetSavedTodayCount.mockReturnValue(1);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
  });

  it('clicking dismiss hides the prompt', () => {
    mockGetSavedTodayCount.mockReturnValue(2);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    expect(screen.getByRole('status')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('clicking dismiss sets the day-keyed localStorage flag', () => {
    mockGetSavedTodayCount.mockReturnValue(1);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(localStorage.getItem(DISMISSED_KEY)).toBe(todayIso());
  });

  it('does not show prompt when already dismissed today (flag pre-set)', () => {
    localStorage.setItem(DISMISSED_KEY, todayIso());
    mockGetSavedTodayCount.mockReturnValue(5);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('shows prompt again if dismissed flag is from a previous day', () => {
    localStorage.setItem(DISMISSED_KEY, '2020-01-01');
    mockGetSavedTodayCount.mockReturnValue(2);
    renderWithProviders(<ReflectPage />, { route: '/reflect' });
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
