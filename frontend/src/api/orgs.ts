import { api } from './client'
import type { DocumentItem, InviteResponse, Organization, OrgDetail, OrgRole } from '../types'

export async function createOrg(name: string): Promise<Organization> {
  const { data } = await api.post<Organization>('/orgs', { name })
  return data
}

export async function listOrgs(): Promise<Organization[]> {
  const { data } = await api.get<Organization[]>('/orgs')
  return data
}

export async function getOrg(id: number): Promise<OrgDetail> {
  const { data } = await api.get<OrgDetail>(`/orgs/${id}`)
  return data
}

export async function inviteMember(
  orgId: number,
  email: string,
  role: OrgRole = 'member',
): Promise<InviteResponse> {
  const { data } = await api.post<InviteResponse>(`/orgs/${orgId}/invite`, { email, role })
  return data
}

export async function acceptInvite(token: string): Promise<Organization> {
  const { data } = await api.post<Organization>(`/orgs/invites/${token}/accept`)
  return data
}

export async function removeMember(orgId: number, userId: number): Promise<void> {
  await api.delete(`/orgs/${orgId}/members/${userId}`)
}

export async function publishDocument(documentId: number, orgId: number): Promise<DocumentItem> {
  const { data } = await api.patch<DocumentItem>(`/documents/${documentId}/publish`, {
    org_id: orgId,
  })
  return data
}

export async function unpublishDocument(documentId: number): Promise<DocumentItem> {
  const { data } = await api.delete<DocumentItem>(`/documents/${documentId}/unpublish`)
  return data
}
