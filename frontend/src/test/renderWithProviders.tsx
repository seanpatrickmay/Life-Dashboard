/**
 * Test helper: wraps a component with QueryClientProvider + ThemeProvider + MemoryRouter.
 * Usage: renderWithProviders(<MyComponent />, { route: '/read' })
 */
import { type ReactElement } from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'styled-components';
import { MemoryRouter } from 'react-router-dom';
import type { DefaultTheme } from 'styled-components';

export const testTheme: DefaultTheme = {
  fonts: { heading: 'sans-serif', body: 'sans-serif' },
  mode: 'dark',
  intensity: 'rich',
  shadows: {
    soft: '0 2px 8px rgba(0,0,0,0.3)',
    hard: '0 4px 16px rgba(0,0,0,0.5)',
  },
  palette: {
    neutral: {
      '50': '#fafafa',
      '200': '#e5e5e5',
      '700': '#525252',
      '900': '#171717',
    },
    pond: {
      '200': '#7ED7C4',
    },
    bloom: {
      '200': '#f9a8d4',
      '300': '#f472b6',
    },
  },
  colors: {
    surfaceRaised: '#1e1e2e',
    overlay: 'rgba(0,0,0,0.3)',
    overlayHover: 'rgba(0,0,0,0.1)',
    overlayActive: 'rgba(0,0,0,0.2)',
    textPrimary: '#fff',
    textSecondary: '#aaa',
    borderSubtle: '#333',
    focusRing: '#7ED7C4',
    scrollThumb: '#555',
    scrollTrack: '#222',
    accent: '#7ED7C4',
    backgroundCard: 'rgba(20,28,46,0.94)',
    surfaceInset: 'rgba(0,0,0,0.12)',
  },
} as unknown as DefaultTheme;

export function renderWithProviders(
  ui: ReactElement,
  options: {
    route?: string;
    queryClient?: QueryClient;
  } = {},
) {
  const { route = '/', queryClient } = options;
  const client =
    queryClient ??
    new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });

  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={testTheme}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}
