import { Route, Routes } from 'react-router-dom';

import { DashboardPage } from './Dashboard';
import { InsightsPage } from './Insights';
import { SettingsPage } from './Settings';
import { GardenPage } from './Garden';
import { NutritionPage } from './Nutrition';
import { UserPage } from './User';
import { PageShell } from '../components/layout/PageShell';
import { PageBackground } from '../components/layout/PageBackground';
import { useVisitRefresh } from '../hooks/useVisitRefresh';

const routes = [
  { path: '/', element: <DashboardPage /> },
  { path: '/insights', element: <InsightsPage /> },
  { path: '/settings', element: <SettingsPage /> },
  { path: '/garden', element: <GardenPage /> },
  { path: '/nutrition', element: <NutritionPage /> },
  { path: '/user', element: <UserPage /> }
];

function App() {
  useVisitRefresh();
  return (
    <PageBackground className="flatten-textures">
      <PageShell>
        <Routes>
          {routes.map((route) => (
            <Route key={route.path} path={route.path} element={route.element} />
          ))}
        </Routes>
      </PageShell>
    </PageBackground>
  );
}

export default App;
