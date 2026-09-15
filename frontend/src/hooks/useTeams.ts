import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  acceptTeamInvite,
  approveTeamJoinRequest,
  createTeam,
  createTeamInvite,
  deleteTeam,
  deleteTeamDocument,
  getTeam,
  getTeamConversation,
  listPendingInvites,
  listTeamConversations,
  listTeamDocuments,
  listTeamJoinRequests,
  listTeamMembers,
  listTeamMessages,
  listTeams,
  markTeamMessageRead,
  previewInvite,
  previewTeamJoinCode,
  regenerateTeamJoinCode,
  rejectTeamInvite,
  rejectTeamJoinRequest,
  removeTeamMember,
  requestJoinTeam,
  sendTeamMessage,
  teamChatQuery,
  updateTeam,
  uploadTeamDocument,
} from '../api/teams'

export function useTeams() {
  return useQuery({ queryKey: ['teams'], queryFn: listTeams })
}

export function useTeam(teamId: number | null) {
  return useQuery({
    queryKey: ['teams', teamId],
    queryFn: () => getTeam(teamId!),
    enabled: teamId != null,
  })
}

export function useCreateTeam() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createTeam,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['teams'] }),
  })
}

export function useUpdateTeam() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, ...payload }: { teamId: number; name?: string; description?: string }) =>
      updateTeam(teamId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['teams'] }),
  })
}

export function useDeleteTeam() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteTeam,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['teams'] }),
  })
}

export function useTeamMembers(teamId: number | null) {
  return useQuery({
    queryKey: ['teams', teamId, 'members'],
    queryFn: () => listTeamMembers(teamId!),
    enabled: teamId != null,
  })
}

export function useRemoveTeamMember() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      removeTeamMember(teamId, userId),
    onSuccess: (_, { teamId }) => {
      qc.invalidateQueries({ queryKey: ['teams', teamId] })
    },
  })
}

export function usePendingInvites() {
  return useQuery({ queryKey: ['team-invites', 'pending'], queryFn: listPendingInvites })
}

export function useInvitePreview(token: string | null) {
  return useQuery({
    queryKey: ['team-invites', token],
    queryFn: () => previewInvite(token!),
    enabled: !!token,
  })
}

export function useCreateTeamInvite() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, email }: { teamId: number; email: string }) =>
      createTeamInvite(teamId, email),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['team-invites'] }),
  })
}

export function useAcceptTeamInvite() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: acceptTeamInvite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['teams'] })
      qc.invalidateQueries({ queryKey: ['team-invites'] })
    },
  })
}

export function useRejectTeamInvite() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: rejectTeamInvite,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['team-invites'] }),
  })
}

export function usePreviewTeamJoinCode(code: string | null) {
  return useQuery({
    queryKey: ['team-join-preview', code],
    queryFn: () => previewTeamJoinCode(code!),
    enabled: !!code && code.replace(/[-\s]/g, '').length >= 8,
  })
}

export function useRequestJoinTeam() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: requestJoinTeam,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['teams'] })
      qc.invalidateQueries({ queryKey: ['team-join-requests'] })
    },
  })
}

export function useTeamJoinRequests(teamId: number | null) {
  return useQuery({
    queryKey: ['team-join-requests', teamId],
    queryFn: () => listTeamJoinRequests(teamId!),
    enabled: teamId != null,
  })
}

export function useApproveTeamJoinRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, requestId }: { teamId: number; requestId: number }) =>
      approveTeamJoinRequest(teamId, requestId),
    onSuccess: (_, { teamId }) => {
      qc.invalidateQueries({ queryKey: ['teams', teamId] })
      qc.invalidateQueries({ queryKey: ['team-join-requests', teamId] })
      qc.invalidateQueries({ queryKey: ['teams'] })
    },
  })
}

export function useRejectTeamJoinRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, requestId }: { teamId: number; requestId: number }) =>
      rejectTeamJoinRequest(teamId, requestId),
    onSuccess: (_, { teamId }) => {
      qc.invalidateQueries({ queryKey: ['team-join-requests', teamId] })
      qc.invalidateQueries({ queryKey: ['teams', teamId] })
    },
  })
}

export function useRegenerateTeamJoinCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: regenerateTeamJoinCode,
    onSuccess: (_, teamId) => {
      qc.invalidateQueries({ queryKey: ['teams', teamId] })
    },
  })
}

export function useTeamDocuments(teamId: number | null, refetchInterval?: number | false) {
  return useQuery({
    queryKey: ['team-documents', teamId],
    queryFn: () => listTeamDocuments(teamId!),
    enabled: teamId != null,
    refetchInterval,
  })
}

export function useUploadTeamDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, file }: { teamId: number; file: File }) =>
      uploadTeamDocument(teamId, file),
    onSuccess: (_, { teamId }) => {
      qc.invalidateQueries({ queryKey: ['team-documents', teamId] })
    },
  })
}

export function useDeleteTeamDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, documentId }: { teamId: number; documentId: number }) =>
      deleteTeamDocument(teamId, documentId),
    onSuccess: (_, { teamId }) => {
      qc.invalidateQueries({ queryKey: ['team-documents', teamId] })
    },
  })
}

export function useTeamChat() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      teamId,
      ...payload
    }: {
      teamId: number
      question: string
      conversation_id?: number | null
    }) => teamChatQuery(teamId, payload),
    onSuccess: (_, { teamId }) => {
      qc.invalidateQueries({ queryKey: ['team-conversations', teamId] })
    },
  })
}

export function useTeamConversations(teamId: number | null) {
  return useQuery({
    queryKey: ['team-conversations', teamId],
    queryFn: () => listTeamConversations(teamId!),
    enabled: teamId != null,
  })
}

export function useTeamConversation(teamId: number | null, conversationId: number | null) {
  return useQuery({
    queryKey: ['team-conversations', teamId, conversationId],
    queryFn: () => getTeamConversation(teamId!, conversationId!),
    enabled: teamId != null && conversationId != null,
  })
}

export function useTeamMessages(teamId: number | null) {
  return useQuery({
    queryKey: ['team-messages', teamId],
    queryFn: () => listTeamMessages(teamId!),
    enabled: teamId != null,
  })
}

export function useSendTeamMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      teamId,
      ...payload
    }: {
      teamId: number
      content: string
      file_document_id?: number
    }) => sendTeamMessage(teamId, payload),
    onSuccess: (_, { teamId }) => {
      qc.invalidateQueries({ queryKey: ['team-messages', teamId] })
    },
  })
}

export function useMarkTeamMessageRead() {
  return useMutation({
    mutationFn: ({ teamId, messageId }: { teamId: number; messageId: number }) =>
      markTeamMessageRead(teamId, messageId),
  })
}
