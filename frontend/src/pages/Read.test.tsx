// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Routes, Route, MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'styled-components';
import { Navigate } from 'react-router-dom';
import { testTheme } from '../test/renderWithProviders';

// Mock heavy hooks to prevent network calls
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

vi.mock('../hooks/useAIDigest', () => ({
  useAIDigest: () => ({
    digestQuery: { isLoading: false, data: { items: [], narrative: null, last_refreshed: null, item_count: 0, is_stale: false } },
    refreshDigest: vi.fn(),
    isRefreshing: false,
  }),
}));

vi.mock('../hooks/useSkipTracking', () => ({
  useSkipTracking: () => {},
}));

vi.mock('../services/newsFeedService', async () => {
  const actual = await vi.importActual<typeof import('../services/newsFeedService')>('../services/newsFeedService');
  return {
    ...actual,
    getLastRefresh: () => null,
    getReadTodayCount: () => 0,
  };
});

// Minimal stub for ReadPage to confirm it renders
vi.mock('./Read', async () => {
  const { ReadPage: Actual } = await vi.importActual<typeof import('./Read')>('./Read');
  return { ReadPage: Actual };
});

function renderWithRouter(initialPath: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={testTheme}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/read" element={<div data-testid="read-page">Read page</div>} />
            <Route path="/news" element={<Navigate to="/read" replace />} />
            <Route path="/news/profile" element={<Navigate to="/read" replace />} />
            <Route path="/ai-digest" element={<Navigate to="/read" replace />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

describe('Read tab routing', () => {
  it('/read renders the Read page', () => {
    renderWithRouter('/read');
    expect(screen.getByTestId('read-page')).toBeInTheDocument();
  });

  it('/news redirects to /read', () => {
    renderWithRouter('/news');
    expect(screen.getByTestId('read-page')).toBeInTheDocument();
  });

  it('/news/profile redirects to /read', () => {
    renderWithRouter('/news/profile');
    expect(screen.getByTestId('read-page')).toBeInTheDocument();
  });

  it('/ai-digest redirects to /read', () => {
    renderWithRouter('/ai-digest');
    expect(screen.getByTestId('read-page')).toBeInTheDocument();
  });
});
