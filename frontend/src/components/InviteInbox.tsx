import { useState } from 'react'
import {
  useAcceptTeamInvite,
  usePendingInvites,
  useRejectTeamInvite,
} from '../hooks/useTeams'
import { useWorkspaceStore } from '../store/workspaceStore'
import { getErrorMessage } from '../api/client'

export function InviteInbox() {
  const invites = usePendingInvites()
  const accept = useAcceptTeamInvite()
  const reject = useRejectTeamInvite()
  const setTeam = useWorkspaceStore((s) => s.setTeam)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const count = invites.data?.total ?? 0

  async function handleAccept(token: string) {
    setError(null)
    try {
      const team = await accept.mutateAsync(token)
      setTeam(team.id, team.name)
      setOpen(false)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function handleReject(token: string) {
    setError(null)
    try {
      await reject.mutateAsync(token)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-md border border-line bg-panel px-3 py-2 text-sm hover:border-accent"
        title="Team invitations"
      >
        🔔
        {count > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-danger text-[10px] text-white">
            {count}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-lg border border-line bg-panel shadow-lg">
          <div className="border-b border-line px-3 py-2 text-sm font-medium">
            Team invitations
          </div>
          <div className="max-h-80 overflow-y-auto p-2">
            {error ? <p className="mb-2 text-xs text-danger">{error}</p> : null}
            {!invites.data?.invites.length ? (
              <p className="px-2 py-4 text-sm text-ink-muted">No pending invites</p>
            ) : (
              invites.data.invites.map((invite) => (
                <div key={invite.id} className="mb-2 rounded-md border border-line p-3 text-sm">
                  <p className="font-medium">Team #{invite.team_id}</p>
                  <p className="text-xs text-ink-muted">{invite.invited_email}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleAccept(invite.token)}
                      className="rounded-md bg-accent px-2 py-1 text-xs text-white"
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReject(invite.token)}
                      className="rounded-md border border-line px-2 py-1 text-xs"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
