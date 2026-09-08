import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { DocumentViewer } from '../components/DocumentViewer'
import { MessageBubble } from '../components/MessageBubble'
import { MarkdownAnswer } from '../components/MarkdownAnswer'
import { streamQuestion } from '../api/chat'
import {
  useConversation,
  useConversations,
  useDeleteConversation,
} from '../hooks/useChat'
import { useOrgs } from '../hooks/useOrgs'
import { useChatStore } from '../store/chatStore'
import type { Citation } from '../types'
import { useQueryClient } from '@tanstack/react-query'

export function ChatPage() {
  const queryClient = useQueryClient()
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const setActiveConversationId = useChatStore((s) => s.setActiveConversationId)
  const conversations = useConversations()
  const conversation = useConversation(activeConversationId)
  const remove = useDeleteConversation()
  const orgs = useOrgs()

  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null)
  const [question, setQuestion] = useState('')
  const [compare, setCompare] = useState(false)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const [viewerCitation, setViewerCitation] = useState<Citation | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingQuestion, setStreamingQuestion] = useState('')
  const [streamingAnswer, setStreamingAnswer] = useState('')

  const messages = conversation.data?.messages ?? []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, isStreaming, streamingAnswer])

  const bottomRef = useRef<HTMLDivElement>(null)

  const title = useMemo(() => {
    if (!activeConversationId) return 'New conversation'
    return conversation.data?.title || 'Conversation'
  }, [activeConversationId, conversation.data?.title])

  function openCitation(citation: Citation) {
    setSelectedCitation(citation)
    setViewerCitation(citation)
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isStreaming) return

    setError(null)
    setStreamingQuestion(trimmed)
    setStreamingAnswer('')
    setIsStreaming(true)
    setQuestion('')

    await streamQuestion(
      {
        question: trimmed,
        conversation_id: activeConversationId,
        compare,
        org_id: selectedOrgId,
      },
      (token) => {
        setStreamingAnswer((prev) => prev + token)
      },
      async (doneEvent) => {
        if (doneEvent.answer) {
          setStreamingAnswer(doneEvent.answer)
        }
        if (doneEvent.conversation_id) {
          setActiveConversationId(doneEvent.conversation_id)
        }
        if (doneEvent.citations && doneEvent.citations[0]) {
          setSelectedCitation(doneEvent.citations[0])
        }
        await queryClient.invalidateQueries({ queryKey: ['conversations'] })
        if (doneEvent.conversation_id) {
          await queryClient.invalidateQueries({
            queryKey: ['conversation', doneEvent.conversation_id],
          })
        }
        setIsStreaming(false)
        setStreamingQuestion('')
        setStreamingAnswer('')
      },
      (errMessage) => {
        setIsStreaming(false)
        setError(errMessage)
      },
    )
  }

  return (
    <>
      <div className="grid h-[calc(100vh-9rem)] gap-4 lg:grid-cols-[260px_minmax(0,1fr)_280px]">
        {/* Left Sidebar: Conversations */}
        <aside className="flex flex-col overflow-hidden rounded-xl border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-3 py-3">
            <h2 className="text-sm font-semibold">Conversations</h2>
            <button
              type="button"
              onClick={() => {
                setActiveConversationId(null)
                setSelectedCitation(null)
              }}
              className="rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover"
            >
              New
            </button>
          </div>
          <ul className="flex-1 space-y-1 overflow-y-auto p-2">
            {conversations.data?.conversations.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => setActiveConversationId(item.id)}
                  className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                    activeConversationId === item.id
                      ? 'bg-accent-soft text-ink font-medium'
                      : 'text-ink-muted hover:bg-surface'
                  }`}
                >
                  <span className="line-clamp-2">{item.title}</span>
                </button>
              </li>
            ))}
            {!conversations.data?.conversations.length ? (
              <li className="px-3 py-4 text-xs text-ink-muted">No conversations yet.</li>
            ) : null}
          </ul>
        </aside>

        {/* Middle Main Section */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-panel">
          {/* Header with Title and Org Library Selector */}
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div>
              <h1 className="font-semibold text-ink">{title}</h1>
              <p className="text-xs text-ink-muted">Answers grounded in indexed vector store.</p>
            </div>

            <div className="flex items-center gap-3">
              {orgs.data?.length ? (
                <div className="flex items-center gap-1.5">
                  <label className="text-xs text-ink-muted font-medium">Scope:</label>
                  <select
                    value={selectedOrgId || ''}
                    onChange={(e) =>
                      setSelectedOrgId(e.target.value ? Number(e.target.value) : null)
                    }
                    className="rounded-md border border-line bg-surface px-2.5 py-1 text-xs outline-none focus:border-accent"
                  >
                    <option value="">Personal Library</option>
                    {orgs.data.map((o) => (
                      <option key={o.id} value={o.id}>
                        Team: {o.name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}

              {activeConversationId ? (
                <button
                  type="button"
                  className="text-xs text-danger hover:underline"
                  onClick={async () => {
                    if (!confirm('Delete this conversation?')) return
                    await remove.mutateAsync(activeConversationId)
                    setActiveConversationId(null)
                    setSelectedCitation(null)
                  }}
                >
                  Delete
                </button>
              ) : null}
            </div>
          </div>

          {/* Message List */}
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {!messages.length && !isStreaming ? (
              <div className="grid h-full place-items-center text-center">
                <div>
                  <p className="font-display text-3xl text-ink">Ask your knowledge base</p>
                  <p className="mt-2 text-sm text-ink-muted">
                    Answers stream in real-time grounded in your uploaded documents.
                  </p>
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  onCitationClick={openCitation}
                />
              ))
            )}

            {/* In-flight streaming question & answer animation */}
            {isStreaming ? (
              <>
                <MessageBubble
                  message={{
                    id: 9999991,
                    conversation_id: activeConversationId || 0,
                    role: 'user',
                    content: streamingQuestion,
                    citations: null,
                    created_at: new Date().toISOString(),
                  }}
                  onCitationClick={openCitation}
                />
                <div className="space-y-1 rounded-xl border border-line bg-surface p-4 text-sm text-ink leading-relaxed">
                  <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                    <span>Assistant</span>
                    <span className="inline-block h-2 w-2 rounded-full bg-accent animate-ping" />
                  </div>
                  <MarkdownAnswer content={streamingAnswer} />
                  <span className="inline-block w-2 h-4 ml-0.5 bg-accent align-middle animate-pulse" />
                </div>
              </>
            ) : null}

            <div ref={bottomRef} />
          </div>

          {/* Query Form */}
          <form onSubmit={onSubmit} className="border-t border-line p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-xs text-ink-muted">
                <input
                  type="checkbox"
                  checked={compare}
                  onChange={(e) => setCompare(e.target.checked)}
                />
                Compare across retrieved documents
              </label>
              {error ? <p className="text-xs text-danger">{error}</p> : null}
            </div>
            <div className="flex gap-2">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={2}
                placeholder="Ask a question..."
                className="min-h-[64px] flex-1 resize-none rounded-md border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void onSubmit(e)
                  }
                }}
              />
              <button
                type="submit"
                disabled={isStreaming || !question.trim()}
                className="self-end rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </form>
        </section>

        {/* Right Sidebar: Citation Details */}
        <aside className="hidden overflow-hidden rounded-xl border border-line bg-panel lg:flex lg:flex-col">
          <div className="border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold">Citation detail</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {selectedCitation ? (
              <div className="space-y-3">
                <div>
                  <p className="text-sm font-semibold">
                    {selectedCitation.document || `Document #${selectedCitation.document_id}`}
                  </p>
                  <p className="text-xs text-ink-muted">
                    {selectedCitation.page_number != null
                      ? `Page ${selectedCitation.page_number}`
                      : 'Page n/a'}
                    {selectedCitation.section ? ` · ${selectedCitation.section}` : ''}
                  </p>
                </div>
                <p className="rounded-md bg-surface p-3 text-sm leading-relaxed text-ink">
                  {selectedCitation.text || 'No excerpt available.'}
                </p>
                <button
                  type="button"
                  onClick={() => setViewerCitation(selectedCitation)}
                  className="rounded-md bg-accent px-3 py-2 text-xs font-semibold text-white hover:bg-accent-hover"
                >
                  Open in source viewer
                </button>
                <p className="text-xs text-ink-muted">
                  Similarity {selectedCitation.similarity_score.toFixed(3)}
                </p>
              </div>
            ) : (
              <p className="text-sm text-ink-muted">
                Click a source under an answer to open the document viewer with highlighting.
              </p>
            )}
          </div>
        </aside>
      </div>

      {viewerCitation ? (
        <DocumentViewer citation={viewerCitation} onClose={() => setViewerCitation(null)} />
      ) : null}
    </>
  )
}