import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
} from '@tanstack/react-query';

import App from './pages/App';
import { GlobalStyle } from './theme/GlobalStyle';
import { ThemeProvider as AppThemeProvider } from './theme/ThemeProvider';
import { emitToast } from './components/common/Toast';

// ---------------------------------------------------------------------------
// Error extraction helper
// ---------------------------------------------------------------------------

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    // Axios wraps the response in error.message; check for response data first
    const axiosLike = error as {
      response?: { data?: { detail?: string; message?: string } };
    };
    const detail = axiosLike.response?.data?.detail;
    if (typeof detail === 'string' && detail.length > 0) return detail;
    const msg = axiosLike.response?.data?.message;
    if (typeof msg === 'string' && msg.length > 0) return msg;
    if (error.message.length > 0) return error.message;
  }
  return 'Something went wrong';
}

// ---------------------------------------------------------------------------
// QueryClient with global error handlers
// ---------------------------------------------------------------------------

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 401) return;

      // Only toast if the query has no cached data (avoid spamming on
      // background refetch failures when stale data is still visible).
      if (query.state.data === undefined) {
        emitToast(extractErrorMessage(error), 'error');
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 401) return;
      if ((mutation.options.meta as Record<string, unknown>)?.suppressToast) return;
      emitToast(extractErrorMessage(error), 'error');
    },
  }),
});

function Root() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppThemeProvider>
        <GlobalStyle />
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AppThemeProvider>
    </QueryClientProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
