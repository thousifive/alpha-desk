import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router'

import { Layout } from './components/Layout'
import { LoginPage } from './features/auth/LoginPage'
import { RequireAuth } from './features/auth/RequireAuth'
import { BranchPage } from './features/branch/BranchPage'
import { DashboardPage } from './features/dashboard/DashboardPage'

// Exercise route pulls in DuckDB-WASM + Monaco (multi-MB); split it out of the main bundle.
const ExercisePage = lazy(() => import('./features/exercise/ExercisePage'))

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <Layout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: 'branches/:branchId', element: <BranchPage /> },
          {
            path: 'exercises/:slug',
            element: (
              <Suspense
                fallback={<p className="p-6 font-mono text-sm text-muted">Loading desk…</p>}
              >
                <ExercisePage />
              </Suspense>
            ),
          },
        ],
      },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
