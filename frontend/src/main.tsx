import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ApiError } from './api/client'
import App from './App'
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
// Best effort: paint the cached dashboard on the first frame. Rendering doesn't wait on it
// for long, since IndexedDB reads take milliseconds.
await primeSnapshot(queryClient)

const root = document.getElementById('root')
if (!root) throw new Error('#root missing from index.html')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
