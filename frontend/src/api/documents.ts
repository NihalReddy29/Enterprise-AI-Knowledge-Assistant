import { api } from './client'
import type { DocumentHighlight, DocumentItem } from '../types'

export async function listDocuments(): Promise<{ documents: DocumentItem[]; total: number }> {
  const { data } = await api.get<{ documents: DocumentItem[]; total: number }>('/documents/')
  return data
}

export async function uploadDocument(file: File): Promise<{ document: DocumentItem; message: string }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<{ document: DocumentItem; message: string }>(
    '/documents/upload',
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  )
  return data
}

export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/documents/${id}`)
}

export async function getDocument(id: number): Promise<DocumentItem> {
  const { data } = await api.get<DocumentItem>(`/documents/${id}`)
  return data
}

export async function fetchDocumentFile(id: number): Promise<Blob> {
  const { data } = await api.get<Blob>(`/documents/${id}/file`, {
    responseType: 'blob',
  })
  return data
}

export async function fetchDocumentHighlight(params: {
  documentId: number
  excerpt: string
  pageNumber?: number | null
  section?: string | null
}): Promise<DocumentHighlight> {
  const { data } = await api.get<DocumentHighlight>(`/documents/${params.documentId}/highlight`, {
    params: {
      excerpt: params.excerpt,
      page_number: params.pageNumber ?? undefined,
      section: params.section ?? undefined,
    },
  })
  return data
}
