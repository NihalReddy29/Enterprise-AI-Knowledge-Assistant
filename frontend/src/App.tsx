import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from './components/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AdminPage } from './pages/Admin'
import { ChatPage } from './pages/Chat'
import { DashboardPage } from './pages/Dashboard'
import { DocumentsPage } from './pages/Documents'
import { LoginPage } from './pages/Login'
import { InviteAcceptPage } from './pages/InviteAccept'
import { TeamMessengerPage } from './pages/TeamMessenger'
import { TeamsPage } from './pages/Teams'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/invites/:token" element={<InviteAcceptPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="teams" element={<TeamsPage />} />
              <Route path="messenger" element={<TeamMessengerPage />} />
              <Route path="admin" element={<AdminPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
