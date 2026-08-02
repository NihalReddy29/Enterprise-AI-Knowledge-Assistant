import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { getErrorMessage } from '../api/client'
import { useLogin, useRegister } from '../hooks/useAuth'
import { useAuthStore } from '../store/authStore'

export function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const login = useLogin()
  const register = useRegister()
  const token = useAuthStore((s) => s.token)
  const navigate = useNavigate()

  const pending = login.isPending || register.isPending
  const subtitle = useMemo(
    () =>
      mode === 'login'
        ? 'Sign in to search and chat over your company knowledge.'
        : 'Create an account. The first user becomes admin.',
    [mode],
  )

  if (token) {
    return <Navigate to="/" replace />
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      if (mode === 'register') {
        await register.mutateAsync({ name, email, password })
        await login.mutateAsync({ email, password })
      } else {
        await login.mutateAsync({ email, password })
      }
      navigate('/')
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-surface">
      <div className="absolute inset-0 bg-[linear-gradient(135deg,#10231f_0%,#0f766e_48%,#d9f3ef_100%)] opacity-95" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.18),transparent_35%)]" />
      <div className="relative mx-auto flex min-h-screen max-w-6xl items-center px-4 py-10 md:px-8">
        <div className="grid w-full gap-10 md:grid-cols-[1.1fr_0.9fr] md:items-center">
          <section className="text-white">
            <p className="font-display text-5xl leading-none md:text-6xl">Knowledge Assistant</p>
            <p className="mt-4 max-w-md text-base text-white/85 md:text-lg">
              Upload internal documents. Ask grounded questions. Get answers with citations.
            </p>
          </section>

          <section className="rounded-2xl bg-panel p-6 shadow-[0_30px_80px_rgba(16,35,31,0.25)] md:p-8">
            <div className="mb-6 flex gap-2">
              <button
                type="button"
                onClick={() => setMode('login')}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  mode === 'login' ? 'bg-accent text-white' : 'text-ink-muted'
                }`}
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => setMode('register')}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  mode === 'register' ? 'bg-accent text-white' : 'text-ink-muted'
                }`}
              >
                Register
              </button>
            </div>
            <p className="mb-5 text-sm text-ink-muted">{subtitle}</p>
            <form className="space-y-4" onSubmit={onSubmit}>
              {mode === 'register' ? (
                <label className="block space-y-1.5 text-sm">
                  <span className="font-medium">Name</span>
                  <input
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full rounded-md border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
                  />
                </label>
              ) : null}
              <label className="block space-y-1.5 text-sm">
                <span className="font-medium">Email</span>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-md border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
                />
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="font-medium">Password</span>
                <input
                  required
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
                />
              </label>
              {error ? <p className="text-sm text-danger">{error}</p> : null}
              <button
                type="submit"
                disabled={pending}
                className="w-full rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-60"
              >
                {pending ? 'Please wait…' : mode === 'login' ? 'Enter workspace' : 'Create account'}
              </button>
            </form>
            <p className="mt-4 text-xs text-ink-muted">
              Backend API expected at <code>/api/v1</code>.{' '}
              <Link to="/" className="text-accent underline-offset-2 hover:underline">
                Continue if already signed in
              </Link>
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
