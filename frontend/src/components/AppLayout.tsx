import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/chat', label: 'Chat' },
  { to: '/documents', label: 'Documents' },
]

export function AppLayout() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-surface text-ink">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,243,239,0.7),transparent_35%),radial-gradient(circle_at_bottom_right,rgba(213,226,220,0.55),transparent_40%)]" />
      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 md:px-6">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
          <div>
            <p className="font-display text-2xl tracking-tight text-ink">Knowledge Assistant</p>
            <p className="text-sm text-ink-muted">Enterprise document intelligence</p>
          </div>
          <nav className="flex flex-wrap items-center gap-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-accent text-white'
                      : 'text-ink-muted hover:bg-accent-soft hover:text-ink'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
            {user?.role === 'admin' && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-accent text-white'
                      : 'text-ink-muted hover:bg-accent-soft hover:text-ink'
                  }`
                }
              >
                Admin
              </NavLink>
            )}
          </nav>
          <div className="flex items-center gap-3 text-sm">
            <div className="text-right">
              <p className="font-medium">{user?.name}</p>
              <p className="text-ink-muted capitalize">{user?.role}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/login')
              }}
              className="rounded-md border border-line bg-panel px-3 py-2 text-sm hover:border-accent"
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 pb-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
