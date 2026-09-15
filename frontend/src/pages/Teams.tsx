import { useState } from 'react'
import { getErrorMessage } from '../api/client'
import {
  useApproveTeamJoinRequest,
  useCreateTeamInvite,
  useDeleteTeam,
  useRegenerateTeamJoinCode,
  useRejectTeamJoinRequest,
  useRemoveTeamMember,
  useTeam,
  useTeamJoinRequests,
  useTeams,
  useUpdateTeam,
} from '../hooks/useTeams'
import { useWorkspaceStore } from '../store/workspaceStore'
export function TeamsPage() {
  const teams = useTeams()
  const setTeam = useWorkspaceStore((s) => s.setTeam)
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null)
  const activeTeamId = selectedTeamId ?? teams.data?.[0]?.id ?? null
  const teamDetail = useTeam(activeTeamId)
  const isAdmin =
    teamDetail.data?.my_role === 'owner' || teamDetail.data?.my_role === 'admin'
  const joinRequests = useTeamJoinRequests(isAdmin ? activeTeamId : null)
  const updateTeam = useUpdateTeam()
  const deleteTeam = useDeleteTeam()
  const inviteMember = useCreateTeamInvite()
  const removeMember = useRemoveTeamMember()
  const approveJoin = useApproveTeamJoinRequest()
  const rejectJoin = useRejectTeamJoinRequest()
  const regenerateCode = useRegenerateTeamJoinCode()

  const [inviteEmail, setInviteEmail] = useState('')
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function copyJoinCode() {
    if (!teamDetail.data?.join_code) return
    await navigator.clipboard.writeText(teamDetail.data.join_code)
    setSuccess('Join code copied to clipboard')
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    if (!activeTeamId || !inviteEmail.trim()) return
    setError(null)
    try {
      const res = await inviteMember.mutateAsync({
        teamId: activeTeamId,
        email: inviteEmail.trim(),
      })
      setInviteEmail('')
      setSuccess(`Invitation sent to ${res.invited_email}`)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault()
    if (!activeTeamId) return
    setError(null)
    try {
      await updateTeam.mutateAsync({
        teamId: activeTeamId,
        name: editName || undefined,
        description: editDescription,
      })
      setSuccess('Team updated')
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl tracking-tight">Team settings</h1>
        <p className="mt-2 text-ink-muted">
          Manage teams, invite members, and configure shared workspaces.
        </p>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-danger">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          {success}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <aside className="rounded-xl border border-line bg-panel p-3">
          <p className="mb-2 text-xs font-semibold uppercase text-ink-muted">Your teams</p>
          <ul className="space-y-1">
            {teams.data?.map((team) => (
              <li key={team.id}>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedTeamId(team.id)
                    setEditName(team.name)
                    setEditDescription(team.description || '')
                  }}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                    activeTeamId === team.id ? 'bg-accent-soft text-accent' : 'hover:bg-surface'
                  }`}
                >
                  {team.name}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {teamDetail.data ? (
          <div className="space-y-6">
            <div className="rounded-xl border border-line bg-panel p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold">{teamDetail.data.name}</h2>
                  <p className="text-sm text-ink-muted">{teamDetail.data.description}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setTeam(teamDetail.data!.id, teamDetail.data!.name)}
                  className="rounded-md bg-accent px-3 py-2 text-sm text-white"
                >
                  Switch to this workspace
                </button>
              </div>
            </div>

            {isAdmin ? (
              <form onSubmit={handleUpdate} className="rounded-xl border border-line bg-panel p-4 space-y-3">
                <h3 className="font-medium">Rename team</h3>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-md border border-line px-3 py-2 text-sm"
                />
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={2}
                  className="w-full rounded-md border border-line px-3 py-2 text-sm"
                  placeholder="Description"
                />
                <button type="submit" className="rounded-md bg-accent px-3 py-2 text-sm text-white">
                  Save changes
                </button>
              </form>
            ) : null}

            {isAdmin && teamDetail.data.join_code ? (
              <div className="rounded-xl border border-line bg-panel p-4 space-y-3">
                <h3 className="font-medium">Team join code</h3>
                <p className="text-sm text-ink-muted">
                  Share this code so others can request to join. You approve each request.
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <code className="rounded-md bg-surface px-3 py-2 text-lg font-mono tracking-widest">
                    {teamDetail.data.join_code}
                  </code>
                  <button
                    type="button"
                    onClick={copyJoinCode}
                    className="rounded-md border border-line px-3 py-2 text-sm"
                  >
                    Copy
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      if (!activeTeamId || !confirm('Generate a new code? The old code will stop working.')) {
                        return
                      }
                      setError(null)
                      try {
                        await regenerateCode.mutateAsync(activeTeamId)
                        setSuccess('New join code generated')
                      } catch (err) {
                        setError(getErrorMessage(err))
                      }
                    }}
                    className="rounded-md border border-line px-3 py-2 text-sm"
                  >
                    Regenerate
                  </button>
                </div>
              </div>
            ) : null}

            {isAdmin && (joinRequests.data?.total ?? teamDetail.data.pending_join_request_count) ? (
              <div className="rounded-xl border border-line bg-panel">
                <div className="border-b border-line px-4 py-3 font-medium">
                  Pending join requests ({joinRequests.data?.total ?? 0})
                </div>
                <ul className="divide-y divide-line">
                  {joinRequests.data?.requests.map((request) => (
                    <li
                      key={request.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
                    >
                      <div>
                        <p className="font-medium">{request.user_name || request.user_email}</p>
                        {request.message ? (
                          <p className="text-ink-muted">{request.message}</p>
                        ) : null}
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            activeTeamId &&
                            approveJoin.mutate({ teamId: activeTeamId, requestId: request.id })
                          }
                          className="rounded-md bg-accent px-3 py-1.5 text-xs text-white"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            activeTeamId &&
                            rejectJoin.mutate({ teamId: activeTeamId, requestId: request.id })
                          }
                          className="rounded-md border border-line px-3 py-1.5 text-xs text-danger"
                        >
                          Decline
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {isAdmin ? (
              <form onSubmit={handleInvite} className="rounded-xl border border-line bg-panel p-4 space-y-3">
                <h3 className="font-medium">Invite member</h3>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="email@company.com"
                  className="w-full rounded-md border border-line px-3 py-2 text-sm"
                />
                <button type="submit" className="rounded-md bg-accent px-3 py-2 text-sm text-white">
                  Send invite
                </button>
              </form>
            ) : null}

            <div className="rounded-xl border border-line bg-panel">
              <div className="border-b border-line px-4 py-3 font-medium">Members</div>
              <ul className="divide-y divide-line">
                {teamDetail.data.members.map((member) => (
                  <li
                    key={member.id}
                    className="flex items-center justify-between px-4 py-3 text-sm"
                  >
                    <div>
                      <p className="font-medium">{member.user_name || member.user_email}</p>
                      <p className="text-ink-muted capitalize">{member.role}</p>
                    </div>
                    {isAdmin && member.role !== 'owner' ? (
                      <button
                        type="button"
                        onClick={() =>
                          activeTeamId &&
                          removeMember.mutate({ teamId: activeTeamId, userId: member.user_id })
                        }
                        className="text-xs text-danger hover:underline"
                      >
                        Remove
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>

            {teamDetail.data.my_role === 'owner' ? (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                <h3 className="font-medium text-danger">Danger zone</h3>
                <p className="mt-1 text-sm text-ink-muted">
                  Deleting a team removes all documents, chat history, and messenger data.
                </p>
                <button
                  type="button"
                  onClick={async () => {
                    if (!activeTeamId || !confirm('Delete this team permanently?')) return
                    await deleteTeam.mutateAsync(activeTeamId)
                  }}
                  className="mt-3 rounded-md border border-danger px-3 py-2 text-sm text-danger"
                >
                  Delete team
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-ink-muted">Select or create a team from the workspace switcher.</p>
        )}
      </div>
    </div>
  )
}
