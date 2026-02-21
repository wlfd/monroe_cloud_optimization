import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import { AppLayout } from '@/layouts/AppLayout';
import { AuthLayout } from '@/layouts/AuthLayout';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { IngestionPage } from '@/pages/IngestionPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import AnomaliesPage from '@/pages/AnomaliesPage';
import RecommendationsPage from '@/pages/RecommendationsPage';

const router = createBrowserRouter([
  {
    // Public routes (unauthenticated)
    element: <AuthLayout />,
    children: [
      { path: '/login', element: <LoginPage /> },
    ],
  },
  {
    // Authenticated routes — AppLayout redirects to /login if not authenticated
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/ingestion', element: <IngestionPage /> },
      { path: '/anomalies', element: <AnomaliesPage /> },
      { path: '/recommendations', element: <RecommendationsPage /> },
      // Phase 6+ routes slot in here:
      // { path: '/attribution', element: <AttributionPage /> },
      // { path: '/settings', element: <SettingsPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
