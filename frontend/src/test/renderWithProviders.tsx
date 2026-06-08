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
  radii: {
    card: '22px',
    shell: '26px',
    pixel: '6px',
  },
  shadows: {
    soft: '0 2px 8px rgba(0,0,0,0.3)',
    hard: '0 4px 16px rgba(0,0,0,0.5)',
    pixel: '4px 4px 0 0 rgba(0,0,0,0.85)',
    pixelDark: '4px 4px 0 0 rgba(0,0,0,0.55)',
  },
  palette: {
    neutral: {
      '50': '#fafafa',
      '200': '#e5e5e5',
      '700': '#525252',
      '900': '#171717',
    },
    pond: {
      '100': '#B8F0DF',
      '200': '#7ED7C4',
      '300': '#3F9B8A',
      '400': '#2E7568',
    },
    bloom: {
      '200': '#f9a8d4',
      '300': '#f472b6',
    },
  },
  colors: {
    surface: '#18213A',
    surfaceRaised: '#222C49',
    surfaceInset: 'rgba(0,0,0,0.12)',
    overlay: 'rgba(0,0,0,0.3)',
    overlayHover: 'rgba(0,0,0,0.1)',
    overlayActive: 'rgba(0,0,0,0.2)',
    textPrimary: '#fff',
    textSecondary: '#aaa',
    borderStrong: '#E7E0F0',
    borderSoft: '#2F3A5C',
    borderSubtle: '#333',
    focusRing: '#7ED7C4',
    scrollThumb: '#555',
    scrollTrack: '#222',
    accent: '#7ED7C4',
    accentText: '#0F1424',
    accentStrong: '#B8F0DF',
    accentSubtle: '#1C3A39',
    backgroundCard: 'rgba(20,28,46,0.94)',
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
