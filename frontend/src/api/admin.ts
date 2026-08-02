import { api } from './client'
import type {
  AdminDocumentList,
  AdminFeedbackList,
  AdminQueryList,
  AdminStatistics,
  AdminStorageStats,
  User,
} from '../types'

export async function listUsers(): Promise<{ users: User[]; total: number }> {
  const { data } = await api.get<{ users: User[]; total: number }>('/admin/users')
  return data
}

export async function deleteUser(userId: number): Promise<void> {
  await api.delete(`/admin/users/${userId}`)
}

export async function getStatistics(): Promise<AdminStatistics> {
  const { data } = await api.get<AdminStatistics>('/admin/statistics')
  return data
}

export async function listAdminDocuments(): Promise<AdminDocumentList> {
  const { data } = await api.get<AdminDocumentList>('/admin/documents')
  return data
}

export async function getStorageStats(): Promise<AdminStorageStats> {
  const { data } = await api.get<AdminStorageStats>('/admin/storage')
  return data
}

export async function listAdminQueries(): Promise<AdminQueryList> {
  const { data } = await api.get<AdminQueryList>('/admin/queries')
  return data
}

export async function listAdminFeedback(): Promise<AdminFeedbackList> {
  const { data } = await api.get<AdminFeedbackList>('/admin/feedback')
  return data
}
