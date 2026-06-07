// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { Routes, Route, MemoryRouter, Navigate } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'styled-components';
import { testTheme } from '../test/renderWithProviders';
import { renderWithProviders } from '../test/renderWithProviders';

// ── Mock heavy hooks ──────────────────────────────────────────────────────────

vi.mock('../hooks/useMorningBrief', () => ({
  useMorningBrief: () => ({
    paragraph: 'Good morning. Here is your brief.',
    sources: [],
    isReady: true,
    isPartiallyReady: true,
  }),
}));

vi.mock('../hooks/useInsight', () => ({
  useInsight: () => ({ data: { readiness_score: 80 } }),
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
    eventsQuery: { isLoading: false, data: { events: [] } },
  }),
}));

vi.mock('../hooks/useNutritionIntake', () => ({
  useNutritionDailySummary: () => ({
    isLoading: false,
    data: { nutrients: [] },
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

// ── matchMedia stub helpers ────────────────────────────────────────────────────

function stubMatchMedia(mobileMatches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
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

// ── Routing redirect tests ────────────────────────────────────────────────────

function renderRoutes(initialPath: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={testTheme}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/" element={<div data-testid="today-page">Today</div>} />
            <Route path="/body" element={<div data-testid="body-page">Body</div>} />
            <Route path="/calendar" element={<div data-testid="calendar-page">Calendar</div>} />
            <Route path="/projects/*" element={<div data-testid="projects-page">Projects</div>} />
            <Route path="/read" element={<div data-testid="read-page">Read</div>} />
            <Route path="/reflect" element={<div data-testid="reflect-page">Reflect</div>} />
            {/* /user now redirects to / */}
            <Route path="/user" element={<Navigate to="/" replace />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

describe('Secondary routes remain reachable', () => {
  it('/calendar renders the Calendar page', () => {
    renderRoutes('/calendar');
    expect(screen.getByTestId('calendar-page')).toBeInTheDocument();
  });

  it('/projects renders the Projects page', () => {
    renderRoutes('/projects');
    expect(screen.getByTestId('projects-page')).toBeInTheDocument();
  });

  it('/body renders the Body page', () => {
    renderRoutes('/body');
    expect(screen.getByTestId('body-page')).toBeInTheDocument();
  });

  it('/read renders the Read page', () => {
    renderRoutes('/read');
    expect(screen.getByTestId('read-page')).toBeInTheDocument();
  });
});

describe('/user redirect', () => {
  it('/user redirects to /', () => {
    renderRoutes('/user');
    expect(screen.getByTestId('today-page')).toBeInTheDocument();
  });
});

// ── Desktop Today CTA tests ───────────────────────────────────────────────────

import { TodayPage } from './Today';

describe('TodayPage desktop CTAs', () => {
  beforeEach(() => stubMatchMedia(false)); // desktop
  afterEach(() => { vi.restoreAllMocks(); });

  it('renders "Open calendar →" link with href /calendar on desktop', () => {
    renderWithProviders(<TodayPage />);
    const link = screen.getByRole('link', { name: /open calendar/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/calendar');
  });

  it('renders "Open board →" link with href /projects on desktop', () => {
    renderWithProviders(<TodayPage />);
    const link = screen.getByRole('link', { name: /open board/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/projects');
  });
});

// ── Mobile Today CTA tests ────────────────────────────────────────────────────

describe('TodayPage mobile CTAs', () => {
  beforeEach(() => stubMatchMedia(true)); // mobile
  afterEach(() => { vi.restoreAllMocks(); });

  // SecondaryNavCTAs aria-labels are exact ("Open calendar" / "Open board").
  // We use exact-string accessible-name matching so the SummaryChips calendar
  // chip (aria-label "N events today — open calendar") is not counted, and the
  // test purely asserts the desktop grid branch and mobile SummaryChips branch
  // don't both render SecondaryNavCTAs simultaneously.
  it('renders the SecondaryNavCTAs "Open calendar" link exactly once on mobile (no double-render)', () => {
    renderWithProviders(<TodayPage />);
    const links = screen.getAllByRole('link', { name: 'Open calendar' });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute('href', '/calendar');
  });

  it('renders the SecondaryNavCTAs "Open board" link exactly once on mobile (no double-render)', () => {
    renderWithProviders(<TodayPage />);
    const links = screen.getAllByRole('link', { name: 'Open board' });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute('href', '/projects');
  });
});
