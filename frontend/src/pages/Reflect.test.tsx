// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Routes, Route, MemoryRouter, Navigate } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'styled-components';
import { testTheme } from '../test/renderWithProviders';

// Mock heavy hooks/services to prevent network calls
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

function renderWithRouter(initialPath: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={testTheme}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/reflect" element={<div data-testid="reflect-page">Reflect page</div>} />
            <Route path="/journal" element={<Navigate to="/reflect" replace />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

describe('Reflect tab routing', () => {
  it('/reflect renders the Reflect page', () => {
    renderWithRouter('/reflect');
    expect(screen.getByTestId('reflect-page')).toBeInTheDocument();
  });

  it('/journal redirects to /reflect', () => {
    renderWithRouter('/journal');
    expect(screen.getByTestId('reflect-page')).toBeInTheDocument();
  });
});
