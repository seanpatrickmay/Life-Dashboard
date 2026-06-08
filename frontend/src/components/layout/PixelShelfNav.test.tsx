// @vitest-environment jsdom
/**
 * PixelShelfNav a11y tests — verify that the pixel-shelf restyle does NOT
 * break accessibility semantics on any nav site.
 *
 * Covers:
 *   (a) Desktop primary nav (PageShell) — aria-current="page" on active NavLink
 *   (b) Mobile BottomNav          — aria-current="page" on active NavLink
 *   (c) Body sub-nav tablist      — role="tab" + aria-selected on Tab buttons
 */
import '@testing-library/jest-dom/vitest';
import { screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { renderWithProviders } from '../../test/renderWithProviders';
import { BottomNav } from './BottomNav';
import { PageShell } from './PageShell';

// ── PageShell mocks (mirrors BottomNav.test.tsx) ──────────────────────────────

vi.mock('./CloudNavShelf', () => ({
  CloudNavShelf: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="cloud-nav-shelf">{children}</div>
  ),
}));

vi.mock('../dashboard/MonetChatPanel', () => ({
  MonetChatBubble: () => null,
}));

vi.mock('./SettingsDrawer', () => ({
  SettingsDrawer: ({ onClose }: { onClose: () => void }) => (
    <div role="dialog" data-testid="settings-drawer">
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

vi.mock('../../demo/guest/guestMode', () => ({
  isGuestMode: () => false,
  exitGuestMode: vi.fn(),
}));

vi.mock('../../demo/guest/guestStore', () => ({
  clearGuestState: vi.fn(),
}));

function stubDesktop() {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: false, // desktop: matchMedia('(max-width: 640px)') → false
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

function stubMobile() {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: true, // mobile
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

// ── (a) Desktop primary nav — aria-current ────────────────────────────────────

describe('pixel-shelf: desktop primary nav a11y semantics', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubDesktop();
  });

  it('active Today NavLink carries aria-current="page" at route /', () => {
    renderWithProviders(
      <PageShell>
        <div>content</div>
      </PageShell>,
      { route: '/' },
    );
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const todayLink = within(nav).getByRole('link', { name: /today/i });
    expect(todayLink).toHaveAttribute('aria-current', 'page');
  });

  it('inactive Read NavLink does NOT carry aria-current at route /', () => {
    renderWithProviders(
      <PageShell>
        <div>content</div>
      </PageShell>,
      { route: '/' },
    );
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const readLink = within(nav).getByRole('link', { name: /read/i });
    expect(readLink).not.toHaveAttribute('aria-current', 'page');
  });

  it('active Read NavLink carries aria-current="page" at route /read', () => {
    renderWithProviders(
      <PageShell>
        <div>content</div>
      </PageShell>,
      { route: '/read' },
    );
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const readLink = within(nav).getByRole('link', { name: /read/i });
    expect(readLink).toHaveAttribute('aria-current', 'page');
  });

  it('active Reflect NavLink carries aria-current="page" at route /reflect', () => {
    renderWithProviders(
      <PageShell>
        <div>content</div>
      </PageShell>,
      { route: '/reflect' },
    );
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const reflectLink = within(nav).getByRole('link', { name: /reflect/i });
    expect(reflectLink).toHaveAttribute('aria-current', 'page');
  });
});

// ── (b) Mobile BottomNav — aria-current ───────────────────────────────────────

describe('pixel-shelf: mobile BottomNav a11y semantics', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubMobile();
  });

  it('Today link has aria-current="page" when on /', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/' });
    expect(screen.getByRole('link', { name: /today/i })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('Read link has aria-current="page" when on /read', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/read' });
    expect(screen.getByRole('link', { name: /read/i })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('Reflect link has aria-current="page" when on /reflect', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/reflect' });
    expect(screen.getByRole('link', { name: /reflect/i })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('inactive links do NOT carry aria-current="page"', () => {
    renderWithProviders(<BottomNav onMore={vi.fn()} />, { route: '/read' });
    const todayLink = screen.getByRole('link', { name: /today/i });
    const reflectLink = screen.getByRole('link', { name: /reflect/i });
    expect(todayLink).not.toHaveAttribute('aria-current', 'page');
    expect(reflectLink).not.toHaveAttribute('aria-current', 'page');
  });
});

// ── (c) Body sub-nav tablist — role="tab" + aria-selected ────────────────────

import { BodyPage } from '../../pages/Body';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'styled-components';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { render } from '@testing-library/react';
import { testTheme } from '../../test/renderWithProviders';

vi.mock('../../hooks/useInsight', () => ({
  useInsight: () => ({
    data: { readiness_score: 78, readiness_label: 'Good', hrv: [], rhr: [], sleep: [], load: [] },
  }),
}));

vi.mock('../../hooks/useNutritionIntake', () => ({
  useNutritionDailySummary: () => ({
    isLoading: false,
    data: { nutrients: [] },
  }),
  useNutritionHistory: () => ({ data: { nutrients: [] }, isLoading: false }),
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
  useNutritionFoods: () => ({ foodsQuery: { isLoading: false, data: [] } }),
}));

vi.mock('../../hooks/useNutritionGoals', () => ({
  useNutritionGoals: () => ({
    goalsQuery: { isLoading: false, data: [] },
    updateGoal: vi.fn(),
  }),
}));

function renderBody(path = '/body') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={testTheme}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/body" element={<BodyPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe('pixel-shelf: Body sub-nav tablist a11y semantics', () => {
  beforeAll(() => {
    if (typeof window.ResizeObserver === 'undefined') {
      window.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      };
    }
  });

  it('tablist has role="tablist" and aria-label', () => {
    renderBody();
    expect(screen.getByRole('tablist', { name: /body sections/i })).toBeInTheDocument();
  });

  it('Health tab has role="tab" and aria-selected="true" by default', () => {
    renderBody();
    const tab = screen.getByRole('tab', { name: /health/i });
    expect(tab).toHaveAttribute('aria-selected', 'true');
  });

  it('Nutrition tab has role="tab" and aria-selected="false" by default', () => {
    renderBody();
    const tab = screen.getByRole('tab', { name: /nutrition/i });
    expect(tab).toHaveAttribute('aria-selected', 'false');
  });

  it('visiting /body?tab=nutrition gives Nutrition aria-selected="true"', () => {
    renderBody('/body?tab=nutrition');
    expect(screen.getByRole('tab', { name: /nutrition/i })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('tab', { name: /health/i })).toHaveAttribute(
      'aria-selected',
      'false',
    );
  });

  it('tab buttons are connected to their panels via aria-controls', () => {
    renderBody();
    const healthTab = screen.getByRole('tab', { name: /health/i });
    expect(healthTab).toHaveAttribute('aria-controls', 'body-panel-health');
    const nutritionTab = screen.getByRole('tab', { name: /nutrition/i });
    expect(nutritionTab).toHaveAttribute('aria-controls', 'body-panel-nutrition');
  });
});
