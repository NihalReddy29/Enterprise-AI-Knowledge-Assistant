import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { DocumentViewer } from '../components/DocumentViewer'
import { MessageBubble } from '../components/MessageBubble'
import { getErrorMessage } from '../api/client'
import {
  useAskQuestion,
  useConversation,
  useConversations,
  useDeleteConversation,
} from '../hooks/useChat'
import { useChatStore } from '../store/chatStore'
import type { Citation } from '../types'

export function ChatPage() {
  const activeConversationId = useChatStore((s) => s.activeConversationId)
  const setActiveConversationId = useChatStore((s) => s.setActiveConversationId)
  const conversations = useConversations()
  const conversation = useConversation(activeConversationId)
  const ask = useAskQuestion()
  const remove = useDeleteConversation()

  const [question, setQuestion] = useState('')
  const [compare, setCompare] = useState(false)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const [viewerCitation, setViewerCitation] = useState<Citation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const messages = conversation.data?.messages ?? []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, ask.isPending])

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
    if (!trimmed || ask.isPending) return
    setError(null)
    try {
      const result = await ask.mutateAsync({
        question: trimmed,
        conversation_id: activeConversationId,
        compare,
      })
      setActiveConversationId(result.conversation_id)
      setQuestion('')
      if (result.citations[0]) setSelectedCitation(result.citations[0])
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <>
      <div className="grid h-[calc(100vh-9rem)] gap-4 lg:grid-cols-[260px_minmax(0,1fr)_280px]">
        <aside className="flex flex-col overflow-hidden rounded-xl border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-3 py-3">
            <h2 className="text-sm font-semibold">Conversations</h2>
            <button
              type="button"
              onClick={() => {
                setActiveConversationId(null)
                setSelectedCitation(null)
              }}
              className="rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-white"
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
                      ? 'bg-accent-soft text-ink'
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

        <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <div>
              <h1 className="font-semibold">{title}</h1>
              <p className="text-xs text-ink-muted">Answers are grounded in indexed documents.</p>
            </div>
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

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {!messages.length && !ask.isPending ? (
              <div className="grid h-full place-items-center text-center">
                <div>
                  <p className="font-display text-3xl">Ask your knowledge base</p>
                  <p className="mt-2 text-sm text-ink-muted">
                    Try “What is our leave policy?” after uploading documents.
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
            {ask.isPending ? (
              <div className="text-sm text-ink-muted">Retrieving context and generating answer…</div>
            ) : null}
            <div ref={bottomRef} />
          </div>

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
                placeholder="Ask a question…"
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
                disabled={ask.isPending || !question.trim()}
                className="self-end rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </form>
        </section>

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
