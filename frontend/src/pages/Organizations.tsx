import { useState } from 'react'
import { getErrorMessage } from '../api/client'
import {
  useAcceptInvite,
  useCreateOrg,
  useInviteMember,
  useOrg,
  useOrgs,
  useRemoveMember,
} from '../hooks/useOrgs'
import type { OrgRole } from '../types'

export function OrganizationsPage() {
  const orgs = useOrgs()
  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null)
  const activeOrgId = selectedOrgId ?? orgs.data?.[0]?.id ?? null

  const orgDetail = useOrg(activeOrgId)
  const createOrgMutation = useCreateOrg()
  const inviteMemberMutation = useInviteMember()
  const removeMemberMutation = useRemoveMember()
  const acceptInviteMutation = useAcceptInvite()

  // Form states
  const [newOrgName, setNewOrgName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<OrgRole>('member')
  const [acceptToken, setAcceptToken] = useState('')
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault()
    if (!newOrgName.trim()) return
    setError(null)
    setSuccess(null)
    try {
      const created = await createOrgMutation.mutateAsync(newOrgName.trim())
      setNewOrgName('')
      setSelectedOrgId(created.id)
      setSuccess(`Organization "${created.name}" created!`)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    if (!activeOrgId || !inviteEmail.trim()) return
    setError(null)
    setSuccess(null)
    setLastInviteUrl(null)
    try {
      const res = await inviteMemberMutation.mutateAsync({
        orgId: activeOrgId,
        email: inviteEmail.trim(),
        role: inviteRole,
      })
      setInviteEmail('')
      setLastInviteUrl(window.location.origin + res.invite_url)
      setSuccess(`Invitation created for ${res.email}!`)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function handleAccept(e: React.FormEvent) {
    e.preventDefault()
    if (!acceptToken.trim()) return
    setError(null)
    setSuccess(null)
    try {
      const org = await acceptInviteMutation.mutateAsync(acceptToken.trim())
      setAcceptToken('')
      setSelectedOrgId(org.id)
      setSuccess(`Joined organization "${org.name}"!`)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl tracking-tight">Teams & Organizations</h1>
        <p className="mt-2 text-ink-muted">
          Manage team workspaces, invite members, and share document libraries.
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

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        {/* Left Column: Org List & Create/Accept */}
        <div className="space-y-4">
          <div className="rounded-xl border border-line bg-panel p-4">
            <h2 className="text-sm font-semibold text-ink mb-3">Your Organizations</h2>
            {orgs.isLoading ? (
              <p className="text-xs text-ink-muted">Loading organizations…</p>
            ) : orgs.data?.length ? (
              <ul className="space-y-1">
                {orgs.data.map((org) => (
                  <li key={org.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedOrgId(org.id)}
                      className={`w-full rounded-md px-3 py-2 text-left text-sm flex items-center justify-between ${
                        activeOrgId === org.id
                          ? 'bg-accent-soft text-ink font-medium'
                          : 'text-ink-muted hover:bg-surface'
                      }`}
                    >
                      <span className="truncate">{org.name}</span>
                      <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-ink-muted">
                        {org.member_count}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-ink-muted">No organizations yet.</p>
            )}
          </div>

          {/* Create Org Box */}
          <form onSubmit={handleCreateOrg} className="rounded-xl border border-line bg-panel p-4">
            <h3 className="text-sm font-semibold text-ink mb-2">Create New Team</h3>
            <div className="space-y-2">
              <input
                type="text"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="Team / Org Name"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button
                type="submit"
                disabled={createOrgMutation.isPending || !newOrgName.trim()}
                className="w-full rounded-md bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
              >
                Create Organization
              </button>
            </div>
          </form>

          {/* Join with Invite Token */}
          <form onSubmit={handleAccept} className="rounded-xl border border-line bg-panel p-4">
            <h3 className="text-sm font-semibold text-ink mb-2">Join via Invite Token</h3>
            <div className="space-y-2">
              <input
                type="text"
                value={acceptToken}
                onChange={(e) => setAcceptToken(e.target.value)}
                placeholder="Paste token or GUID"
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button
                type="submit"
                disabled={acceptInviteMutation.isPending || !acceptToken.trim()}
                className="w-full rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:bg-surface disabled:opacity-50"
              >
                Accept Invite
              </button>
            </div>
          </form>
        </div>

        {/* Right Column: Selected Org Details & Members */}
        <div className="rounded-xl border border-line bg-panel p-6 space-y-6">
          {orgDetail.isLoading ? (
            <p className="text-sm text-ink-muted">Loading team details…</p>
          ) : orgDetail.data ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
                <div>
                  <h2 className="text-xl font-semibold">{orgDetail.data.name}</h2>
                  <p className="text-xs text-ink-muted">
                    Slug: <code className="rounded bg-surface px-1">{orgDetail.data.slug}</code> · Your Role:{' '}
                    <span className="capitalize font-semibold text-accent">
                      {orgDetail.data.my_role || 'member'}
                    </span>
                  </p>
                </div>
              </div>

              {/* Invite Member Section (Owner / Admin only) */}
              {['owner', 'admin'].includes(orgDetail.data.my_role || '') ? (
                <div className="rounded-lg border border-line bg-surface p-4 space-y-3">
                  <h3 className="text-sm font-semibold text-ink">Invite Team Member</h3>
                  <form onSubmit={handleInvite} className="flex flex-wrap gap-2">
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="teammate@company.com"
                      className="min-w-[200px] flex-1 rounded-md border border-line bg-panel px-3 py-1.5 text-sm outline-none focus:border-accent"
                    />
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as OrgRole)}
                      className="rounded-md border border-line bg-panel px-3 py-1.5 text-sm outline-none"
                    >
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </select>
                    <button
                      type="submit"
                      disabled={inviteMemberMutation.isPending || !inviteEmail.trim()}
                      className="rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
                    >
                      Send Invite
                    </button>
                  </form>
                  {lastInviteUrl ? (
                    <div className="mt-2 rounded bg-panel p-2 text-xs">
                      <p className="font-semibold text-ink-muted">Shareable Invite Link:</p>
                      <code className="select-all break-all text-accent">{lastInviteUrl}</code>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* Members List */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-ink">
                  Members ({orgDetail.data.members.length})
                </h3>
                <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line">
                  {orgDetail.data.members.map((member) => (
                    <li
                      key={member.id}
                      className="flex items-center justify-between p-3 text-sm bg-panel hover:bg-surface"
                    >
                      <div>
                        <p className="font-medium text-ink">
                          {member.user_name || member.user_email}
                        </p>
                        <p className="text-xs text-ink-muted">{member.user_email}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-semibold capitalize text-accent">
                          {member.role}
                        </span>
                        {['owner', 'admin'].includes(orgDetail.data.my_role || '') ? (
                          <button
                            type="button"
                            className="text-xs text-danger hover:underline"
                            onClick={async () => {
                              if (!confirm(`Remove ${member.user_email} from org?`)) return
                              try {
                                await removeMemberMutation.mutateAsync({
                                  orgId: activeOrgId!,
                                  userId: member.user_id,
                                })
                              } catch (err) {
                                alert(getErrorMessage(err))
                              }
                            }}
                          >
                            Remove
                          </button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          ) : (
            <p className="text-sm text-ink-muted">Select or create an organization to view details.</p>
          )}
        </div>
      </div>
    </div>
  )
}
