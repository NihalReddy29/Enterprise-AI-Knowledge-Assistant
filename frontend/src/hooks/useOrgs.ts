import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  acceptInvite,
  createOrg,
  getOrg,
  inviteMember,
  listOrgs,
  publishDocument,
  removeMember,
  unpublishDocument,
} from '../api/orgs'
import type { OrgRole } from '../types'

export function useOrgs() {
  return useQuery({
    queryKey: ['orgs'],
    queryFn: listOrgs,
  })
}

export function useOrg(id: number | null) {
  return useQuery({
    queryKey: ['orgs', id],
    queryFn: () => getOrg(id!),
    enabled: !!id,
  })
}

export function useCreateOrg() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => createOrg(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['orgs'] })
    },
  })
}

export function useInviteMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      orgId,
      email,
      role,
    }: {
      orgId: number
      email: string
      role?: OrgRole
    }) => inviteMember(orgId, email, role),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['orgs', variables.orgId] })
    },
  })
}

export function useAcceptInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => acceptInvite(token),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['orgs'] })
    },
  })
}

export function useRemoveMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orgId, userId }: { orgId: number; userId: number }) =>
      removeMember(orgId, userId),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['orgs', variables.orgId] })
    },
  })
}

export function usePublishDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ documentId, orgId }: { documentId: number; orgId: number }) =>
      publishDocument(documentId, orgId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function useUnpublishDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (documentId: number) => unpublishDocument(documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}
