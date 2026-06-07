import { lazy, Suspense } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';

// Lazy load all page components for code splitting
const TodayPage = lazy(() => import('./Today').then(m => ({ default: m.TodayPage })));
const BodyPage = lazy(() => import('./Body').then(m => ({ default: m.BodyPage })));
const ReflectPage = lazy(() => import('./Reflect').then(m => ({ default: m.ReflectPage })));
const CalendarPage = lazy(() => import('./Calendar').then(m => ({ default: m.CalendarPage })));
const ProjectsPage = lazy(() => import('./Projects').then(m => ({ default: m.ProjectsPage })));
const ReadPage = lazy(() => import('./Read').then(m => ({ default: m.ReadPage })));
const UserPage = lazy(() => import('./User').then(m => ({ default: m.UserPage })));
const FoodManagerPage = lazy(() => import('./FoodManagerPage').then(m => ({ default: m.FoodManagerPage })));
const LoginPage = lazy(() => import('./Login').then(m => ({ default: m.LoginPage })));

import { PageShell } from '../components/layout/PageShell';
import { PageBackground } from '../components/layout/PageBackground';
import { useVisitRefresh } from '../hooks/useVisitRefresh';
import { useLocalMidnightInvalidation } from '../hooks/useLocalMidnightInvalidation';
import useNewsContextPrefetch from '../hooks/useNewsContextPrefetch';
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
  { path: '/', element: <TodayPage /> },
  { path: '/body', element: <BodyPage /> },
  { path: '/insights', element: <Navigate to="/body" replace /> },
  { path: '/nutrition', element: <Navigate to="/body?tab=nutrition" replace /> },
  { path: '/reflect', element: <ReflectPage /> },
  { path: '/journal', element: <Navigate to="/reflect" replace /> },
  { path: '/calendar', element: <CalendarPage /> },
  { path: '/projects/*', element: <ProjectsPage /> },
  { path: '/read', element: <ReadPage /> },
  { path: '/news', element: <Navigate to="/read" replace /> },
  { path: '/news/profile', element: <Navigate to="/read" replace /> },
  { path: '/ai-digest', element: <Navigate to="/read" replace /> },
  { path: '/user', element: <UserPage /> },
  { path: '/settings/food-db', element: <FoodManagerPage /> },
];

function ShellLayout() {
  useVisitRefresh();
  useLocalMidnightInvalidation();
  useNewsContextPrefetch();
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