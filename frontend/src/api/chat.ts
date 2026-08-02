import { api } from './client'
import type {
  ChatQueryResponse,
  Conversation,
  ConversationDetail,
} from '../types'

export async function askQuestion(payload: {
  question: string
  conversation_id?: number | null
  document_ids?: number[] | null
  compare?: boolean
}): Promise<ChatQueryResponse> {
  const { data } = await api.post<ChatQueryResponse>('/chat/query', payload)
  return data
}

export async function listConversations(): Promise<{
  conversations: Conversation[]
  total: number
}> {
  const { data } = await api.get<{ conversations: Conversation[]; total: number }>(
    '/chat/conversations',
  )
  return data
}

export async function getConversation(id: number): Promise<ConversationDetail> {
  const { data } = await api.get<ConversationDetail>(`/chat/conversations/${id}`)
  return data
}

export async function deleteConversation(id: number): Promise<void> {
  await api.delete(`/chat/conversations/${id}`)
}

export async function submitFeedback(payload: {
  messageId: number
  rating: 0 | 1
  comment?: string
}): Promise<{ id: number; message_id: number; rating: number; comment: string | null }> {
  const { data } = await api.post(`/chat/messages/${payload.messageId}/feedback`, {
    rating: payload.rating,
    comment: payload.comment,
  })
  return data
}
