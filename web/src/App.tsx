import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { GlobalErrorBoundary } from './components/GlobalErrorBoundary'
import { Layout } from './components/ui/Layout'
import { SessionProvider } from './lib/hooks/useSession'
import { Skeleton } from './components/ui/Skeleton'

const ChatPage = lazy(() => import('./pages/ChatPage'))
const ToolsPage = lazy(() => import('./pages/ToolsPage'))
const StatsPage = lazy(() => import('./pages/StatsPage'))

function PageFallback() {
  return (
    <div className="space-y-4 p-2">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export default function App() {
  return (
    <GlobalErrorBoundary>
      <BrowserRouter>
        <SessionProvider>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route element={<Layout />}>
                <Route path="/" element={<ChatPage />} />
                <Route path="/tools" element={<ToolsPage />} />
                <Route path="/tools/:toolId" element={<ToolsPage />} />
                <Route path="/stats" element={<StatsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </SessionProvider>
      </BrowserRouter>
    </GlobalErrorBoundary>
  )
}
