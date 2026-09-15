import { useState } from 'react'
import {
  useCreateTeam,
  usePreviewTeamJoinCode,
  useRequestJoinTeam,
  useTeams,
} from '../hooks/useTeams'
import { useWorkspaceStore, workspaceLabel } from '../store/workspaceStore'
import { getErrorMessage } from '../api/client'

export function WorkspaceSwitcher() {
  const workspace = useWorkspaceStore((s) => s.workspace)
  const setPersonal = useWorkspaceStore((s) => s.setPersonal)
  const setTeam = useWorkspaceStore((s) => s.setTeam)
  const teams = useTeams()
  const createTeam = useCreateTeam()
  const requestJoin = useRequestJoinTeam()
  const [open, setOpen] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [showJoin, setShowJoin] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [joinCode, setJoinCode] = useState('')
  const [joinMessage, setJoinMessage] = useState('')
  const [joinSuccess, setJoinSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const joinPreview = usePreviewTeamJoinCode(showJoin ? joinCode : null)

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault()
    if (!joinCode.trim()) return
    setError(null)
    setJoinSuccess(null)
    try {
      await requestJoin.mutateAsync({
        join_code: joinCode.trim(),
        message: joinMessage.trim() || undefined,
      })
      setJoinSuccess('Join request sent. A team admin will review it.')
      setJoinCode('')
      setJoinMessage('')
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setError(null)
    try {
      const team = await createTeam.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
      })
      setTeam(team.id, team.name)
      setName('')
      setDescription('')
      setShowCreate(false)
      setOpen(false)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium hover:border-accent"
      >
        <span className="text-ink-muted">Workspace:</span>
        <span>{workspaceLabel(workspace)}</span>
        <span className="text-ink-muted">▾</span>
      </button>

      {open ? (
        <div className="absolute left-0 z-50 mt-2 w-64 rounded-lg border border-line bg-panel shadow-lg">
          <div className="p-2">
            <button
              type="button"
              onClick={() => {
                setPersonal()
                setOpen(false)
              }}
              className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                workspace.type === 'personal'
                  ? 'bg-accent-soft text-accent'
                  : 'hover:bg-surface'
              }`}
            >
              Personal
            </button>
            {teams.data?.map((team) => (
              <button
                key={team.id}
                type="button"
                onClick={() => {
                  setTeam(team.id, team.name)
                  setOpen(false)
                }}
                className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                  workspace.type === 'team' && workspace.teamId === team.id
                    ? 'bg-accent-soft text-accent'
                    : 'hover:bg-surface'
                }`}
              >
                {team.name}
              </button>
            ))}
          </div>
          <div className="border-t border-line p-2 space-y-1">
            {showJoin ? (
              <form onSubmit={handleJoin} className="space-y-2 p-1">
                <input
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                  placeholder="Team code (e.g. ABCD-1234)"
                  className="w-full rounded-md border border-line px-2 py-1.5 text-sm font-mono uppercase"
                />
                {joinPreview.data ? (
                  <p className="text-xs text-ink-muted">
                    Join <span className="font-medium text-ink">{joinPreview.data.team_name}</span>{' '}
                    ({joinPreview.data.member_count} members)
                  </p>
                ) : null}
                <textarea
                  value={joinMessage}
                  onChange={(e) => setJoinMessage(e.target.value)}
                  placeholder="Optional message to admins"
                  rows={2}
                  className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                />
                {joinSuccess ? <p className="text-xs text-emerald-700">{joinSuccess}</p> : null}
                {error ? <p className="text-xs text-danger">{error}</p> : null}
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={requestJoin.isPending}
                    className="rounded-md bg-accent px-2 py-1 text-xs text-white"
                  >
                    Request to join
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowJoin(false)
                      setJoinCode('')
                      setJoinMessage('')
                      setJoinSuccess(null)
                      setError(null)
                    }}
                    className="rounded-md border border-line px-2 py-1 text-xs"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : showCreate ? (
              <form onSubmit={handleCreate} className="space-y-2 p-1">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Team name"
                  className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                />
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Description (optional)"
                  className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                />
                {error ? <p className="text-xs text-danger">{error}</p> : null}
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={createTeam.isPending}
                    className="rounded-md bg-accent px-2 py-1 text-xs text-white"
                  >
                    Create
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowCreate(false)}
                    className="rounded-md border border-line px-2 py-1 text-xs"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreate(true)
                    setShowJoin(false)
                    setError(null)
                  }}
                  className="w-full rounded-md px-3 py-2 text-left text-sm text-accent hover:bg-accent-soft"
                >
                  + Create team
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowJoin(true)
                    setShowCreate(false)
                    setError(null)
                    setJoinSuccess(null)
                  }}
                  className="w-full rounded-md px-3 py-2 text-left text-sm text-accent hover:bg-accent-soft"
                >
                  Join with code
                </button>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
