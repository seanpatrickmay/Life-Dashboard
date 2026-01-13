import { Outlet, Route, Routes } from 'react-router-dom';

import { DashboardPage } from './Dashboard';
import { InsightsPage } from './Insights';
import { NutritionPage } from './Nutrition';
import { UserPage } from './User';
import { LoginPage } from './Login';
import { PageShell } from '../components/layout/PageShell';
import { PageBackground } from '../components/layout/PageBackground';
import { useVisitRefresh } from '../hooks/useVisitRefresh';
import { RequireAuth } from '../components/auth/RequireAuth';

const routes = [
  { path: '/', element: <DashboardPage /> },
  { path: '/insights', element: <InsightsPage /> },
  { path: '/nutrition', element: <NutritionPage /> },
  { path: '/user', element: <UserPage /> }
];

function ShellLayout() {
  useVisitRefresh();
  return (
    <PageShell>
      <Outlet />
    </PageShell>
  );
}

function App() {
  return (
    <PageBackground className="flatten-textures">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<ShellLayout />}>
            {routes.map((route) => (
              <Route key={route.path} path={route.path} element={route.element} />
            ))}
          </Route>
        </Route>
      </Routes>
    </PageBackground>
  );
}

export default App;
