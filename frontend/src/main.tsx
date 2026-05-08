import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { OptimizedSSEProvider } from './context/SSEContext'
import { Toaster } from 'react-hot-toast'
import './index.css'
import App from './App'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Failed to find root element');

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <OptimizedSSEProvider>
            <App />
            <Toaster position="bottom-right" toastOptions={{
              duration: 3000,
              style: {
                background: 'var(--glass-bg)',
                color: 'white',
                border: '1px solid var(--glass-border)',
                backdropFilter: 'blur(10px)',
              }
            }} />
          </OptimizedSSEProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
