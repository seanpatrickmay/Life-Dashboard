// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderWithProviders } from '../test/renderWithProviders';
import { TodayPage } from './Today';

// ── Mock heavy data hooks ─────────────────────────────────────────────────────

vi.mock('../hooks/useMorningBrief', () => ({
  useMorningBrief: () => ({
    paragraph: 'Good morning. Here is your brief for the day.',
    sources: [],
    isReady: true,
    isPartiallyReady: true,
  }),
}));

vi.mock('../hooks/useInsight', () => ({
  useInsight: () => ({ data: { readiness_score: 82 } }),
}));

vi.mock('../hooks/useTodos', () => ({
  useTodos: () => ({
    todosQuery: { isLoading: false, data: [], error: null },
    updateTodo: vi.fn(),
    deleteTodo: vi.fn(),
  }),
}));

vi.mock('../hooks/useCalendar', () => ({
  useCalendarEvents: () => ({
    eventsQuery: {
      isLoading: false,
      data: {
        events: [
          {
            id: 'ev-1',
            summary: 'Team standup',
            start_time: new Date().toISOString(),
            end_time: new Date().toISOString(),
            is_all_day: false,
            location: null,
          },
        ],
      },
    },
  }),
}));

vi.mock('../hooks/useNutritionIntake', () => ({
  useNutritionDailySummary: () => ({
    isLoading: false,
    data: {
      nutrients: [
        {
          slug: 'energy',
          display_name: 'Energy',
          group: 'macros',
          unit: 'kcal',
          amount: 1450,
          goal: 2000,
          percent_of_goal: 72.5,
        },
      ],
    },
  }),
}));

vi.mock('../hooks/useNutritionSuggestions', () => ({
  useNutritionSuggestions: () => ({
    suggestionsQuery: { isLoading: false, data: { suggestions: [] } },
    quickLog: vi.fn(),
    isLogging: false,
  }),
}));

vi.mock('../hooks/useNewsFeed', () => ({
  useNewsFeed: () => ({
    curatedQuery: { isLoading: false, data: { picks: [], more: [], saved: [] } },
    annotationsQuery: { data: {} },
    profileQuery: { data: { narrative: '', topics: [] } },
    feedQuery: { data: [] },
    allQuery: { data: {} },
    refreshFeed: vi.fn(),
    markRead: vi.fn(),
    saveArticle: vi.fn(),
    unsaveArticle: vi.fn(),
    dismissArticle: vi.fn(),
    isRefreshing: false,
  }),
  NEWS_CURATED_KEY: ['news', 'curated'],
}));

// ── matchMedia stub helpers ───────────────────────────────────────────────────

function stubMatchMedia(mobileMatches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      // max-width: 640px → matches when mobileMatches=true
      matches: mobileMatches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }),
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('TodayPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the Morning Brief hero', () => {
    stubMatchMedia(false);
    renderWithProviders(<TodayPage />);
    // MorningBriefCard renders aria-label="Morning brief" on its HeroCard div
    expect(screen.getByLabelText(/morning brief/i)).toBeInTheDocument();
  });

  describe('mobile layout (≤640px)', () => {
    beforeEach(() => stubMatchMedia(true));

    it('does NOT mount DashboardNewsFeed', () => {
      renderWithProviders(<TodayPage />);
      // DashboardNewsFeed renders the heading "Today's Briefing"
      expect(screen.queryByText(/today's briefing/i)).not.toBeInTheDocument();
    });

    it('shows SummaryChips with event and kcal counts', () => {
      renderWithProviders(<TodayPage />);
      // Chips container is present
      expect(screen.getByTestId('summary-chips')).toBeInTheDocument();
      // Event count chip (aria-label contains "event")
      const calLinks = screen.getAllByRole('link', { name: /event/i });
      expect(calLinks.length).toBeGreaterThan(0);
      // Kcal chip
      expect(screen.getByRole('link', { name: /kcal/i })).toBeInTheDocument();
    });

    it('renders Open calendar CTA that routes to /calendar', () => {
      renderWithProviders(<TodayPage />);
      // The CTA has exact accessible name "Open calendar" (no extra words like "today")
      const links = screen.getAllByRole('link', { name: 'Open calendar' });
      expect(links.length).toBeGreaterThan(0);
      expect(links[0]).toHaveAttribute('href', '/calendar');
    });

    it('renders Open board CTA that routes to /projects', () => {
      renderWithProviders(<TodayPage />);
      const link = screen.getByRole('link', { name: 'Open board' });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/projects');
    });

    it('still renders TodoScrollPad on mobile', () => {
      renderWithProviders(<TodayPage />);
      // TodoScrollPad renders a "Task list" heading
      expect(screen.getByText(/task list/i)).toBeInTheDocument();
    });
  });

  describe('desktop layout (>640px)', () => {
    beforeEach(() => stubMatchMedia(false));

    it('renders the supporting grid widgets', () => {
      renderWithProviders(<TodayPage />);
      // DashboardUpcomingEvents renders a heading "Upcoming"
      expect(screen.getByText(/upcoming/i)).toBeInTheDocument();
    });

    it('does NOT show SummaryChips on desktop', () => {
      renderWithProviders(<TodayPage />);
      expect(screen.queryByTestId('summary-chips')).not.toBeInTheDocument();
    });
  });
});
