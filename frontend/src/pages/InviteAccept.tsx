import { Link, useNavigate, useParams } from 'react-router-dom'
import { getErrorMessage } from '../api/client'
import {
  useAcceptTeamInvite,
  useInvitePreview,
  useRejectTeamInvite,
} from '../hooks/useTeams'
import { useAuthStore } from '../store/authStore'
import { useWorkspaceStore } from '../store/workspaceStore'

export function InviteAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const preview = useInvitePreview(token ?? null)
  const accept = useAcceptTeamInvite()
  const reject = useRejectTeamInvite()
  const isLoggedIn = !!useAuthStore((s) => s.token)
  const setTeam = useWorkspaceStore((s) => s.setTeam)
  const navigate = useNavigate()

  async function handleAccept() {
    if (!token) return
    try {
      const team = await accept.mutateAsync(token)
      setTeam(team.id, team.name)
      navigate('/')
    } catch (err) {
      alert(getErrorMessage(err))
    }
  }

  async function handleReject() {
    if (!token) return
    try {
      await reject.mutateAsync(token)
      navigate('/')
    } catch (err) {
      alert(getErrorMessage(err))
    }
  }

  if (!token) {
    return <p className="p-8 text-center text-ink-muted">Invalid invite link</p>
  }

  if (!isLoggedIn) {
    return (
      <div className="mx-auto max-w-md p-8 text-center space-y-4">
        <h1 className="font-display text-2xl">Team invitation</h1>
        <p className="text-ink-muted">Sign in to respond to this invitation.</p>
        <Link to={`/login?redirect=/invites/${token}`} className="text-accent underline">
          Sign in
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md p-8 space-y-4">
      <h1 className="font-display text-2xl">Team invitation</h1>
      {preview.isLoading ? (
        <p className="text-ink-muted">Loading…</p>
      ) : preview.data ? (
        <>
          <p>
            <strong>{preview.data.inviter_name || 'Someone'}</strong> invited you to join{' '}
            <strong>{preview.data.team_name}</strong>.
          </p>
          {preview.data.team_description ? (
            <p className="text-sm text-ink-muted">{preview.data.team_description}</p>
          ) : null}
          <p className="text-xs text-ink-muted">Status: {preview.data.status}</p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleAccept}
              disabled={accept.isPending || preview.data.status !== 'pending'}
              className="rounded-md bg-accent px-4 py-2 text-sm text-white"
            >
              Accept
            </button>
            <button
              type="button"
              onClick={handleReject}
              disabled={reject.isPending}
              className="rounded-md border border-line px-4 py-2 text-sm"
            >
              Reject
            </button>
          </div>
        </>
      ) : (
        <p className="text-danger">Invite not found or expired.</p>
      )}
    </div>
  )
}
