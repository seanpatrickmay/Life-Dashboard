// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeAll, beforeEach } from 'vitest';

import { renderWithProviders } from '../../test/renderWithProviders';
import { NutritionContent } from './NutritionContent';

// ── Browser API stubs ──────────────────────────────────────────────────────────

beforeAll(() => {
  if (typeof window.ResizeObserver === 'undefined') {
    window.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

// ── Hook mocks — vi.mock factory refs so we can override per-test ─────────────

const mockDailySummary = vi.fn();
const mockHistory = vi.fn();

vi.mock('../../hooks/useNutritionIntake', () => ({
  useNutritionDailySummary: (...args: unknown[]) => mockDailySummary(...args),
  useNutritionHistory: (...args: unknown[]) => mockHistory(...args),
}));

vi.mock('../../hooks/useNutritionSuggestions', () => ({
  useNutritionSuggestions: () => ({
    suggestionsQuery: { isLoading: false, data: { suggestions: [] } },
    quickLog: vi.fn(),
    isLogging: false,
  }),
}));

vi.mock('../../hooks/useNutritionMenu', () => ({
  useNutritionMenu: () => ({
    menuQuery: { isLoading: false, data: { entries: [] } },
    updateEntry: vi.fn(),
    deleteEntry: vi.fn(),
  }),
}));

vi.mock('../../hooks/useNutritionFoods', () => ({
  useNutritionFoods: () => ({
    foodsQuery: { isLoading: false, data: [] },
  }),
}));

vi.mock('../../hooks/useNutritionGoals', () => ({
  useNutritionGoals: () => ({
    goalsQuery: { isLoading: false, data: [] },
    updateGoal: vi.fn(),
  }),
}));

vi.mock('../../hooks/useNutritionNutrients', () => ({
  useNutritionNutrients: () => ({ isLoading: false, data: [] }),
}));

// ── Default happy-path values reset before each test ──────────────────────────

beforeEach(() => {
  mockDailySummary.mockReturnValue({
    isLoading: false,
    isError: false,
    data: {
      nutrients: [
        {
          slug: 'calories',
          display_name: 'Calories',
          group: 'macro',
          unit: 'kcal',
          amount: 1450,
          goal: 2000,
          percent_of_goal: 72.5,
        },
      ],
    },
  });

  mockHistory.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { nutrients: [] },
  });
});

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('NutritionContent', () => {
  describe('error state', () => {
    it('shows a calm error notice when useNutritionDailySummary isError', () => {
      mockDailySummary.mockReturnValue({
        isLoading: false,
        isError: true,
        data: undefined,
      });

      renderWithProviders(<NutritionContent />);

      expect(
        screen.getByText(/couldn't load nutrition data/i)
      ).toBeInTheDocument();
    });

    it('still renders section toggle headers even when primary query errors', () => {
      mockDailySummary.mockReturnValue({
        isLoading: false,
        isError: true,
        data: undefined,
      });

      renderWithProviders(<NutritionContent />);

      // Sections that don't depend on the daily summary still render
      expect(screen.getByText(/quick log/i)).toBeInTheDocument();
      expect(screen.getByText(/today'?s meals/i)).toBeInTheDocument();
    });
  });

  describe('happy path', () => {
    it('renders section toggles when data loads normally', () => {
      renderWithProviders(<NutritionContent />);

      expect(screen.getByText(/quick log/i)).toBeInTheDocument();
      expect(screen.getByText(/today'?s meals/i)).toBeInTheDocument();
      expect(screen.getAllByText(/vitamins/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/14-day averages/i)).toBeInTheDocument();
      expect(screen.getAllByText(/nutrient goals/i).length).toBeGreaterThan(0);
    });

    it('does not render error notice on happy path', () => {
      renderWithProviders(<NutritionContent />);

      expect(
        screen.queryByText(/couldn't load nutrition data/i)
      ).not.toBeInTheDocument();
    });
  });
});
