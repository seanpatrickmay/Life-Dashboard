import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import App from './pages/App';
import { GlobalStyle } from './theme/GlobalStyle';
import { ThemeProvider as AppThemeProvider } from './theme/ThemeProvider';

const queryClient = new QueryClient();


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
