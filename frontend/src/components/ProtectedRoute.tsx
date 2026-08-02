import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useCurrentUser } from '../hooks/useAuth'

export function ProtectedRoute() {
  const token = useAuthStore((s) => s.token)
  const location = useLocation()
  const { isLoading, isError } = useCurrentUser(Boolean(token))

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center text-ink-muted">
        Loading workspace…
      </div>
    )
  }

  if (isError) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
