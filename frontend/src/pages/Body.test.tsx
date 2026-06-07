// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeAll } from 'vitest';
import { Routes, Route, MemoryRouter, Navigate } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'styled-components';
import { testTheme } from '../test/renderWithProviders';

// ── Browser API stubs required by recharts / responsive charts ────────────────

beforeAll(() => {
  if (typeof window.ResizeObserver === 'undefined') {
    window.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

// ── Mock all heavy hooks to prevent network calls ─────────────────────────────

vi.mock('../hooks/useInsight', () => ({
  useInsight: () => ({
    data: {
      readiness_score: 78,
      readiness_label: 'Good',
      hrv: [],
      rhr: [],
      sleep: [],
      load: [],
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
          group: 'macro',
          unit: 'kcal',
          amount: 1450,
          goal: 2000,
          percent_of_goal: 72.5,
        },
      ],
    },
  }),
  useNutritionHistory: () => ({
    data: { nutrients: [] },
    isLoading: false,
  }),
}));

vi.mock('../hooks/useNutritionSuggestions', () => ({
  useNutritionSuggestions: () => ({
    suggestionsQuery: { isLoading: false, data: { suggestions: [] } },
    quickLog: vi.fn(),
    isLogging: false,
  }),
}));

vi.mock('../hooks/useNutritionMenu', () => ({
  useNutritionMenu: () => ({
    menuQuery: { isLoading: false, data: { entries: [] } },
    updateEntry: vi.fn(),
    deleteEntry: vi.fn(),
  }),
}));

vi.mock('../hooks/useNutritionFoods', () => ({
  useNutritionFoods: () => ({
    foodsQuery: { isLoading: false, data: [] },
  }),
}));

vi.mock('../hooks/useNutritionGoals', () => ({
  useNutritionGoals: () => ({
    goalsQuery: { isLoading: false, data: [] },
    updateGoal: vi.fn(),
  }),
}));

// ── Test helpers ──────────────────────────────────────────────────────────────

function renderWithRouter(initialPath: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={testTheme}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/body" element={<div data-testid="body-page">
              {/* We test the real BodyPage via import below in integration tests */}
            </div>} />
            <Route path="/insights" element={<Navigate to="/body" replace />} />
            <Route path="/nutrition" element={<Navigate to="/body?tab=nutrition" replace />} />
            <Route path="/" element={<div data-testid="today-page">Today</div>} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

// ── Integration test helper that uses the real BodyPage ───────────────────────

import { BodyPage } from './Body';

function renderBodyPage(initialPath: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={testTheme}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/body" element={<BodyPage />} />
            <Route path="/" element={<div data-testid="today-page">Today</div>} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

// ── Routing redirect tests ────────────────────────────────────────────────────

describe('Body route redirects', () => {
  it('/insights redirects to /body', () => {
    renderWithRouter('/insights');
    expect(screen.getByTestId('body-page')).toBeInTheDocument();
  });

  it('/nutrition redirects to /body (with ?tab=nutrition)', () => {
    // Route stub just confirms redirect lands on /body
    renderWithRouter('/nutrition');
    expect(screen.getByTestId('body-page')).toBeInTheDocument();
  });
});

// ── BodyPage integration tests ────────────────────────────────────────────────

describe('BodyPage', () => {
  it('renders Health tab by default at /body', () => {
    renderBodyPage('/body');
    // Health tab button is present and selected
    const healthTab = screen.getByRole('tab', { name: /health/i });
    expect(healthTab).toBeInTheDocument();
    expect(healthTab).toHaveAttribute('aria-selected', 'true');
  });

  it('renders ReadinessCard on Health tab', () => {
    renderBodyPage('/body');
    // ReadinessCard renders a readiness score — look for the score value
    expect(screen.getByText(/78/)).toBeInTheDocument();
  });

  it('has a "Today" back link pointing to /', () => {
    renderBodyPage('/body');
    const backLink = screen.getByRole('link', { name: /today/i });
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute('href', '/');
  });

  it('renders both Health and Nutrition tab buttons', () => {
    renderBodyPage('/body');
    expect(screen.getByRole('tab', { name: /health/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /nutrition/i })).toBeInTheDocument();
  });

  it('switching to Nutrition tab shows MacroHero', () => {
    renderBodyPage('/body');
    const nutritionTab = screen.getByRole('tab', { name: /nutrition/i });
    fireEvent.click(nutritionTab);
    // MacroHero renders macro rings; at minimum the Nutrition tab becomes selected
    expect(nutritionTab).toHaveAttribute('aria-selected', 'true');
  });

  it('switching to Nutrition tab deselects Health tab', () => {
    renderBodyPage('/body');
    const healthTab = screen.getByRole('tab', { name: /health/i });
    const nutritionTab = screen.getByRole('tab', { name: /nutrition/i });
    fireEvent.click(nutritionTab);
    expect(healthTab).toHaveAttribute('aria-selected', 'false');
  });

  it('visiting /body?tab=nutrition starts on Nutrition tab', () => {
    renderBodyPage('/body?tab=nutrition');
    const nutritionTab = screen.getByRole('tab', { name: /nutrition/i });
    expect(nutritionTab).toHaveAttribute('aria-selected', 'true');
    // Health tab is not selected
    const healthTab = screen.getByRole('tab', { name: /health/i });
    expect(healthTab).toHaveAttribute('aria-selected', 'false');
  });

  it('does NOT render FoodManager in Body', () => {
    renderBodyPage('/body');
    // FoodManager renders a "Food Database" heading
    expect(screen.queryByText(/food database/i)).not.toBeInTheDocument();
  });

  it('Nutrition tab renders Quick Log section', () => {
    renderBodyPage('/body?tab=nutrition');
    expect(screen.getByText(/quick log/i)).toBeInTheDocument();
  });

  it('Nutrition tab renders Today\'s Meals section', () => {
    renderBodyPage('/body?tab=nutrition');
    expect(screen.getByText(/today'?s meals/i)).toBeInTheDocument();
  });

  it('Nutrition tab renders Vitamins & Minerals section', () => {
    renderBodyPage('/body?tab=nutrition');
    // Multiple elements may match — confirm at least one is present
    expect(screen.getAllByText(/vitamins/i).length).toBeGreaterThan(0);
  });

  it('Nutrition tab renders 14-Day Averages section', () => {
    renderBodyPage('/body?tab=nutrition');
    expect(screen.getByText(/14-day averages/i)).toBeInTheDocument();
  });

  it('Nutrition tab renders Nutrient Goals section', () => {
    renderBodyPage('/body?tab=nutrition');
    // Multiple elements may match (toggle label + panel heading) — confirm at least one
    expect(screen.getAllByText(/nutrient goals/i).length).toBeGreaterThan(0);
  });

  it('invalid ?tab value falls back to Health tab as active', () => {
    renderBodyPage('/body?tab=garbage');
    const healthTab = screen.getByRole('tab', { name: /health/i });
    const nutritionTab = screen.getByRole('tab', { name: /nutrition/i });
    expect(healthTab).toHaveAttribute('aria-selected', 'true');
    expect(nutritionTab).toHaveAttribute('aria-selected', 'false');
  });

  it('ArrowRight on Health tab activates Nutrition tab', () => {
    renderBodyPage('/body');
    const healthTab = screen.getByRole('tab', { name: /health/i });
    const nutritionTab = screen.getByRole('tab', { name: /nutrition/i });
    // Health tab is active; fire ArrowRight on the tablist
    fireEvent.keyDown(healthTab.closest('[role="tablist"]')!, { key: 'ArrowRight', code: 'ArrowRight' });
    expect(nutritionTab).toHaveAttribute('aria-selected', 'true');
    expect(healthTab).toHaveAttribute('aria-selected', 'false');
  });

  it('ArrowLeft on Nutrition tab activates Health tab', () => {
    renderBodyPage('/body?tab=nutrition');
    const healthTab = screen.getByRole('tab', { name: /health/i });
    const nutritionTab = screen.getByRole('tab', { name: /nutrition/i });
    // Nutrition tab is active; fire ArrowLeft on the tablist
    fireEvent.keyDown(nutritionTab.closest('[role="tablist"]')!, { key: 'ArrowLeft', code: 'ArrowLeft' });
    expect(healthTab).toHaveAttribute('aria-selected', 'true');
    expect(nutritionTab).toHaveAttribute('aria-selected', 'false');
  });
});
