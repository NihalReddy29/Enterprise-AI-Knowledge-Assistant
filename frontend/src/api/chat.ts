import { api, getApiBaseUrl, getAuthToken } from './client'
import type {
  ChatQueryResponse,
  Conversation,
  ConversationDetail,
  StreamDoneEvent,
} from '../types'

export async function askQuestion(payload: {
  question: string
  conversation_id?: number | null
  document_ids?: number[] | null
  compare?: boolean
  org_id?: number | null
}): Promise<ChatQueryResponse> {
  const { data } = await api.post<ChatQueryResponse>('/chat/query', payload)
  return data
}

export async function streamQuestion(
  payload: {
    question: string
    conversation_id?: number | null
    document_ids?: number[] | null
    compare?: boolean
    org_id?: number | null
  },
  onToken: (token: string) => void,
  onDone: (event: StreamDoneEvent & { conversation_id?: number; message_id?: number }) => void,
  onError: (err: string) => void,
): Promise<void> {
  const token = getAuthToken()
  const baseUrl = getApiBaseUrl()

  try {
    const response = await fetch(`${baseUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || `Server error: ${response.status}`)
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported by response')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let meta: { conversation_id?: number; message_id?: number } = {}
    let doneEvent: StreamDoneEvent | null = null

    const processLines = (lines: string[]) => {
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith(':')) continue

        if (trimmed.startsWith('data: [DONE]')) {
          const raw = trimmed.slice('data: [DONE]'.length).trim()
          try {
            doneEvent = JSON.parse(raw) as StreamDoneEvent
          } catch (e) {
            console.error('Failed to parse DONE event', e)
          }
        } else if (trimmed.startsWith('data: [META]')) {
          const raw = trimmed.slice('data: [META]'.length).trim()
          try {
            meta = JSON.parse(raw)
          } catch (e) {
            console.error('Failed to parse META event', e)
          }
        } else if (trimmed.startsWith('data: [CORRECTION]')) {
          const raw = trimmed.slice('data: [CORRECTION]'.length).trim()
          try {
            const correction = JSON.parse(raw)
            if (doneEvent && correction.answer) {
              doneEvent.answer = correction.answer
            }
          } catch (e) {
            console.error('Failed to parse CORRECTION event', e)
          }
        } else if (trimmed.startsWith('data:')) {
          const raw = trimmed.slice('data:'.length).trim()
          try {
            const parsed = JSON.parse(raw)
            if (parsed.token) {
              onToken(parsed.token)
            }
          } catch (e) {
            console.error('Failed to parse token event', e)
          }
        }
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      processLines(lines)
    }

    if (buffer.trim()) {
      processLines([buffer])
    }

    if (doneEvent) {
      const finalEvent: StreamDoneEvent = doneEvent
      onDone({
        ...finalEvent,
        conversation_id: meta.conversation_id,
        message_id: meta.message_id,
      })
    } else {
      onError('Stream ended without receiving completion payload.')
    }
  } catch (err: any) {
    onError(err.message || 'Streaming failed')
  }
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
