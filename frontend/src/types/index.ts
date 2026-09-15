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
  org_id?: number | null
  team_id?: number | null
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

export type OrgRole = 'owner' | 'admin' | 'member'

export interface OrgMember {
  id: number
  org_id: number
  user_id: number
  role: OrgRole
  joined_at: string
  user_email?: string | null
  user_name?: string | null
}

export interface Organization {
  id: number
  name: string
  slug: string
  created_by: number | null
  created_at: string
  member_count: number
  my_role?: OrgRole | null
}

export interface OrgDetail extends Organization {
  members: OrgMember[]
}

export type TeamMemberRole = 'owner' | 'admin' | 'member'
export type TeamInviteStatus = 'pending' | 'accepted' | 'rejected' | 'expired' | 'revoked'

export interface Team {
  id: number
  name: string
  description: string | null
  owner_id: number
  qdrant_collection_name: string
  created_at: string
  updated_at: string
  member_count: number
  my_role?: TeamMemberRole | null
}

export interface TeamMember {
  id: number
  team_id: number
  user_id: number
  role: TeamMemberRole
  status: string
  joined_at: string
  user_email?: string | null
  user_name?: string | null
}

export type TeamJoinRequestStatus = 'pending' | 'approved' | 'rejected'

export interface TeamJoinCodePreview {
  team_id: number
  team_name: string
  team_description: string | null
  member_count: number
}

export interface TeamJoinRequest {
  id: number
  team_id: number
  user_id: number
  status: TeamJoinRequestStatus
  message: string | null
  reviewed_by: number | null
  created_at: string
  responded_at: string | null
  user_email?: string | null
  user_name?: string | null
}

export interface TeamDetail extends Team {
  members: TeamMember[]
  join_code?: string | null
  pending_join_request_count?: number
}

export interface TeamInvite {
  id: number
  team_id: number
  invited_email: string
  invited_by: number | null
  token: string
  status: TeamInviteStatus
  created_at: string
  responded_at: string | null
  expires_at: string | null
  invite_url?: string | null
}

export interface TeamInvitePreview {
  team_name: string
  team_description: string | null
  inviter_name: string | null
  inviter_email: string | null
  status: TeamInviteStatus
  expires_at: string | null
}

export interface TeamChatMessage {
  id: number
  team_id: number
  conversation_id: number
  user_id: number | null
  role: string
  content: string
  citations: Citation[] | null
  created_at: string
  author_name?: string | null
}

export interface TeamConversation {
  id: number
  team_id: number
  title: string
  created_at: string
}

export interface TeamConversationDetail extends TeamConversation {
  messages: TeamChatMessage[]
}

export interface TeamChatQueryResponse {
  conversation_id: number
  question: string
  answer: string
  citations: Citation[]
  message_id: number
  provider: string
  model: string
  insufficient_information: boolean
}

export interface TeamMessengerMessage {
  id: number
  team_id: number
  sender_id: number
  content: string
  message_type: 'text' | 'file'
  file_document_id: number | null
  reply_to_id: number | null
  created_at: string
  edited_at: string | null
  deleted_at: string | null
  sender_name?: string | null
  read_by_user_ids: number[]
}

export interface InviteResponse {
  id: number
  org_id: number
  email: string
  role: OrgRole
  token: string
  invite_url: string
  created_at: string
}

export interface StreamDoneEvent {
  answer: string
  citations: Citation[]
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
