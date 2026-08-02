export type UserRole = 'admin' | 'employee'

export interface User {
  id: number
  name: string
  email: string
  role: UserRole
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export type DocumentStatus =
  | 'pending'
  | 'processing'
  | 'extracted'
  | 'indexed'
  | 'failed'

export interface DocumentItem {
  id: number
  filename: string
  file_type: string
  owner_id: number
  file_size: number
  page_count: number | null
  chunk_count: number | null
  status: DocumentStatus
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface Citation {
  index: number
  document: string | null
  document_id: number
  page_number: number | null
  section: string | null
  text: string
  similarity_score: number
}

export interface HighlightMatch {
  start: number
  end: number
  matched_text: string
}

export interface DocumentHighlight {
  document_id: number
  filename: string
  file_type: string
  page_number: number
  section: string | null
  page_text: string
  excerpt: string
  matches: HighlightMatch[]
  total_pages: number | null
}

export interface Conversation {
  id: number
  user_id: number
  title: string
  created_at: string
}

export interface ChatMessage {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  citations: Citation[] | null
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[]
}

export interface ChatQueryResponse {
  conversation_id: number
  question: string
  answer: string
  citations: Citation[]
  message_id: number
  provider: string
  model: string
  insufficient_information: boolean
}

export interface AdminStatistics {
  total_users: number
  total_documents: number
  total_questions: number
  total_conversations: number
  total_feedback: number
  helpful_feedback: number
  not_helpful_feedback: number
  indexed_documents: number
  failed_documents: number
  storage_bytes: number
  storage_mb: number
  most_searched_topics: { topic: string; count: number }[]
}

export interface AdminStorageStats {
  total_documents: number
  total_bytes: number
  total_mb: number
  by_status: Record<string, number>
  by_type: { file_type: string; count: number; total_bytes: number }[]
}

export interface AdminQueryItem {
  id: number
  user_id: number
  conversation_id: number | null
  message_id: number | null
  question: string
  topic: string | null
  provider: string | null
  citation_count: number
  insufficient_information: boolean
  created_at: string
  user_email: string | null
  user_name: string | null
}

export interface AdminQueryList {
  queries: AdminQueryItem[]
  total: number
}

export interface AdminFeedbackItem {
  id: number
  message_id: number
  rating: number
  comment: string | null
  created_at: string
  message_content: string | null
  user_email: string | null
}

export interface AdminFeedbackList {
  feedback: AdminFeedbackItem[]
  total: number
}

export interface AdminDocumentList {
  documents: DocumentItem[]
  total: number
}
