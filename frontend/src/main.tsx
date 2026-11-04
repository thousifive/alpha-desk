import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ApiError } from './api/client'
import App from './App'
import { loadToken } from './lib/auth/token'
import { primeSnapshot, wireLocalInvalidation } from './lib/local/hooks'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Don't hammer the API on 4xx (auth, not found); retry transient failures only.
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
})

wireLocalInvalidation(queryClient)
// Before the first render: the cached dashboard (to paint instantly) and the login token (so
// RequireAuth can decide offline). IndexedDB reads take milliseconds.
await Promise.all([primeSnapshot(queryClient), loadToken()])

const root = document.getElementById('root')
if (!root) throw new Error('#root missing from index.html')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
