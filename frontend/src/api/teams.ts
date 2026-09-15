import { api } from './client'
import type {
  Team,
  TeamChatQueryResponse,
  TeamDetail,
  TeamInvite,
  TeamInvitePreview,
  TeamJoinCodePreview,
  TeamJoinRequest,
  TeamMember,
  TeamMessengerMessage,
  TeamConversation,
  TeamConversationDetail,
} from '../types'

export async function listTeams(): Promise<Team[]> {
  const { data } = await api.get<Team[]>('/teams')
  return data
}

export async function createTeam(payload: {
  name: string
  description?: string
}): Promise<Team> {
  const { data } = await api.post<Team>('/teams', payload)
  return data
}

export async function getTeam(teamId: number): Promise<TeamDetail> {
  const { data } = await api.get<TeamDetail>(`/teams/${teamId}`)
  return data
}

export async function updateTeam(
  teamId: number,
  payload: { name?: string; description?: string },
): Promise<Team> {
  const { data } = await api.patch<Team>(`/teams/${teamId}`, payload)
  return data
}

export async function deleteTeam(teamId: number): Promise<void> {
  await api.delete(`/teams/${teamId}`)
}

export async function listTeamMembers(teamId: number): Promise<TeamMember[]> {
  const { data } = await api.get<TeamMember[]>(`/teams/${teamId}/members`)
  return data
}

export async function removeTeamMember(teamId: number, userId: number): Promise<void> {
  await api.delete(`/teams/${teamId}/members/${userId}`)
}

export async function createTeamInvite(teamId: number, email: string): Promise<TeamInvite> {
  const { data } = await api.post<TeamInvite>(`/teams/${teamId}/invites`, { email })
  return data
}

export async function listPendingInvites(): Promise<{ invites: TeamInvite[]; total: number }> {
  const { data } = await api.get<{ invites: TeamInvite[]; total: number }>(
    '/teams/invites/pending',
  )
  return data
}

export async function previewInvite(token: string): Promise<TeamInvitePreview> {
  const { data } = await api.get<TeamInvitePreview>(`/teams/invites/${token}`)
  return data
}

export async function acceptTeamInvite(token: string): Promise<Team> {
  const { data } = await api.post<Team>(`/teams/invites/${token}/accept`)
  return data
}

export async function rejectTeamInvite(token: string): Promise<void> {
  await api.post(`/teams/invites/${token}/reject`)
}

export async function previewTeamJoinCode(code: string): Promise<TeamJoinCodePreview> {
  const { data } = await api.get<TeamJoinCodePreview>('/teams/join/preview', {
    params: { code },
  })
  return data
}

export async function requestJoinTeam(payload: {
  join_code: string
  message?: string
}): Promise<TeamJoinRequest> {
  const { data } = await api.post<TeamJoinRequest>('/teams/join', payload)
  return data
}

export async function listTeamJoinRequests(
  teamId: number,
): Promise<{ requests: TeamJoinRequest[]; total: number }> {
  const { data } = await api.get<{ requests: TeamJoinRequest[]; total: number }>(
    `/teams/${teamId}/join-requests`,
  )
  return data
}

export async function approveTeamJoinRequest(
  teamId: number,
  requestId: number,
): Promise<TeamMember> {
  const { data } = await api.post<TeamMember>(
    `/teams/${teamId}/join-requests/${requestId}/approve`,
  )
  return data
}

export async function rejectTeamJoinRequest(teamId: number, requestId: number): Promise<void> {
  await api.post(`/teams/${teamId}/join-requests/${requestId}/reject`)
}

export async function regenerateTeamJoinCode(teamId: number): Promise<Team> {
  const { data } = await api.post<Team>(`/teams/${teamId}/join-code/regenerate`)
  return data
}

export async function listTeamDocuments(
  teamId: number,
): Promise<{ documents: import('../types').DocumentItem[]; total: number }> {
  const { data } = await api.get(`/teams/${teamId}/documents`)
  return data
}

export async function uploadTeamDocument(
  teamId: number,
  file: File,
): Promise<{ document: import('../types').DocumentItem; message: string }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post(`/teams/${teamId}/documents/upload`, form)
  return data
}

export async function deleteTeamDocument(teamId: number, documentId: number): Promise<void> {
  await api.delete(`/teams/${teamId}/documents/${documentId}`)
}

export async function teamChatQuery(
  teamId: number,
  payload: {
    question: string
    conversation_id?: number | null
    document_ids?: number[]
    top_k?: number
  },
): Promise<TeamChatQueryResponse> {
  const { data } = await api.post<TeamChatQueryResponse>(`/teams/${teamId}/chat`, payload)
  return data
}

export async function listTeamConversations(teamId: number): Promise<TeamConversation[]> {
  const { data } = await api.get<TeamConversation[]>(`/teams/${teamId}/conversations`)
  return data
}

export async function getTeamConversation(
  teamId: number,
  conversationId: number,
): Promise<TeamConversationDetail> {
  const { data } = await api.get<TeamConversationDetail>(
    `/teams/${teamId}/conversations/${conversationId}`,
  )
  return data
}

export async function listTeamMessages(
  teamId: number,
  params?: { before?: number; limit?: number },
): Promise<{ messages: TeamMessengerMessage[]; total: number; has_more: boolean }> {
  const { data } = await api.get(`/teams/${teamId}/messages`, { params })
  return data
}

export async function sendTeamMessage(
  teamId: number,
  payload: {
    content: string
    message_type?: 'text' | 'file'
    file_document_id?: number
    reply_to_id?: number
  },
): Promise<TeamMessengerMessage> {
  const { data } = await api.post(`/teams/${teamId}/messages`, payload)
  return data
}

export async function markTeamMessageRead(teamId: number, messageId: number): Promise<void> {
  await api.post(`/teams/${teamId}/messages/${messageId}/read`)
}

export function teamMessengerWsUrl(teamId: number, token: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const wsBase = base.replace(/^http/, 'ws').replace(/\/api\/v1$/, '')
  const prefix = base.startsWith('http') ? wsBase : `${window.location.origin.replace(/^http/, 'ws')}`
  const path = `/ws/teams/${teamId}/messenger?token=${encodeURIComponent(token)}`
  if (base.startsWith('http')) {
    return `${prefix}${path}`
  }
  return `${window.location.origin.replace(/^http/, 'ws')}${path}`
}
