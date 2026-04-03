import { lazy, Suspense } from 'react';
import { Outlet, Route, Routes } from 'react-router-dom';

// Lazy load all page components for code splitting
const DashboardPage = lazy(() => import('./Dashboard').then(m => ({ default: m.DashboardPage })));
const InsightsPage = lazy(() => import('./Insights').then(m => ({ default: m.InsightsPage })));
const JournalPage = lazy(() => import('./Journal').then(m => ({ default: m.JournalPage })));
const CalendarPage = lazy(() => import('./Calendar').then(m => ({ default: m.CalendarPage })));
const NutritionPage = lazy(() => import('./Nutrition').then(m => ({ default: m.NutritionPage })));
const ProjectsPage = lazy(() => import('./Projects').then(m => ({ default: m.ProjectsPage })));
const NewsPage = lazy(() => import('./News').then(m => ({ default: m.NewsPage })));
const InterestProfilePage = lazy(() => import('./InterestProfile').then(m => ({ default: m.InterestProfilePage })));
const AIDigestPage = lazy(() => import('./AIDigest').then(m => ({ default: m.AIDigestPage })));
const UserPage = lazy(() => import('./User').then(m => ({ default: m.UserPage })));
const LoginPage = lazy(() => import('./Login').then(m => ({ default: m.LoginPage })));

import { PageShell } from '../components/layout/PageShell';
import { PageBackground } from '../components/layout/PageBackground';
import { useVisitRefresh } from '../hooks/useVisitRefresh';
import { useLocalMidnightInvalidation } from '../hooks/useLocalMidnightInvalidation';
import { RequireAuth } from '../components/auth/RequireAuth';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { ToastProvider } from '../components/common/Toast';

// Simple loading component
const PageLoader = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '200px',
    color: 'rgba(43,27,19,0.5)'
  }}>
    Loading...
  </div>
);

const routes = [
  { path: '/', element: <DashboardPage /> },
  { path: '/insights', element: <InsightsPage /> },
  { path: '/journal', element: <JournalPage /> },
  { path: '/calendar', element: <CalendarPage /> },
  { path: '/projects/*', element: <ProjectsPage /> },
  { path: '/news', element: <NewsPage /> },
  { path: '/news/profile', element: <InterestProfilePage /> },
  { path: '/ai-digest', element: <AIDigestPage /> },
  { path: '/nutrition', element: <NutritionPage /> },
  { path: '/user', element: <UserPage /> }
];

function ShellLayout() {
  useVisitRefresh();
  useLocalMidnightInvalidation();
  return (
    <PageShell>
      <ErrorBoundary>
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </ErrorBoundary>
    </PageShell>
  );
}

function App() {
  return (
    <ToastProvider>
      <PageBackground className="flatten-textures">
        <Routes>
          <Route path="/login" element={
            <Suspense fallback={<PageLoader />}>
              <LoginPage />
            </Suspense>
          } />
          <Route element={<RequireAuth />}>
            <Route element={<ShellLayout />}>
              {routes.map((route) => (
                <Route key={route.path} path={route.path} element={route.element} />
              ))}
            </Route>
          </Route>
        </Routes>
      </PageBackground>
    </ToastProvider>
  );
}

export default App;