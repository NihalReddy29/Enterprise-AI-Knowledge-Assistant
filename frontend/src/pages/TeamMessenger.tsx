import { useEffect, useRef, useState } from 'react'
import { getErrorMessage } from '../api/client'
import { teamMessengerWsUrl } from '../api/teams'
import { useTeamDocuments, useTeamMessages, useSendTeamMessage } from '../hooks/useTeams'
import { useAuthStore } from '../store/authStore'
import { useWorkspaceStore } from '../store/workspaceStore'
import type { TeamMessengerMessage } from '../types'

export function TeamMessengerPage() {
  const workspace = useWorkspaceStore((s) => s.workspace)
  const token = useAuthStore((s) => s.token)
  const user = useAuthStore((s) => s.user)
  const teamId = workspace.type === 'team' ? workspace.teamId : null

  const messagesQuery = useTeamMessages(teamId)
  const sendMessage = useSendTeamMessage()
  const teamDocs = useTeamDocuments(teamId)

  const [messages, setMessages] = useState<TeamMessengerMessage[]>([])
  const [text, setText] = useState('')
  const [showFilePicker, setShowFilePicker] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (messagesQuery.data?.messages) {
      setMessages(messagesQuery.data.messages)
    }
  }, [messagesQuery.data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  useEffect(() => {
    if (!teamId || !token) return

    const ws = new WebSocket(teamMessengerWsUrl(teamId, token))
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'message' && payload.message) {
          setMessages((prev) => {
            if (prev.some((m) => m.id === payload.message.id)) return prev
            return [...prev, payload.message as TeamMessengerMessage]
          })
        }
      } catch {
        // ignore malformed events
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [teamId, token])

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!teamId || !text.trim()) return
    setError(null)
    const content = text.trim()
    setText('')

    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ content }))
      } else {
        const msg = await sendMessage.mutateAsync({ teamId, content })
        setMessages((prev) => [...prev, msg])
      }
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function shareDocument(documentId: number, filename: string) {
    if (!teamId) return
    setShowFilePicker(false)
    try {
      const msg = await sendMessage.mutateAsync({
        teamId,
        content: `Shared file: ${filename}`,
        file_document_id: documentId,
      })
      setMessages((prev) => [...prev, msg])
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  if (workspace.type !== 'team') {
    return (
      <div className="rounded-xl border border-line bg-panel p-8 text-center">
        <p className="text-ink-muted">Select a team workspace to open team messenger.</p>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col rounded-xl border border-line bg-panel">
      <div className="border-b border-line px-4 py-3">
        <h1 className="font-display text-2xl">{workspace.teamName} — Messenger</h1>
        <p className="text-sm text-ink-muted">Real-time chat with your team members</p>
      </div>

      {error ? (
        <p className="px-4 py-2 text-sm text-danger">{error}</p>
      ) : null}

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.map((msg) => {
          const isOwn = msg.sender_id === user?.id
          return (
            <div key={msg.id} className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${
                  isOwn ? 'bg-accent text-white' : 'bg-surface border border-line'
                }`}
              >
                {!isOwn && msg.sender_name ? (
                  <p className="mb-1 text-xs font-semibold opacity-80">{msg.sender_name}</p>
                ) : null}
                <p>{msg.content}</p>
                <p className={`mt-1 text-[10px] ${isOwn ? 'text-white/70' : 'text-ink-muted'}`}>
                  {new Date(msg.created_at).toLocaleTimeString()}
                  {msg.read_by_user_ids.length > 1 ? ' ✓✓' : ''}
                </p>
              </div>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="flex gap-2 border-t border-line p-4">
        <button
          type="button"
          onClick={() => setShowFilePicker((v) => !v)}
          className="rounded-md border border-line px-3 py-2 text-sm"
          title="Share a team document"
        >
          📎
        </button>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a message…"
          className="flex-1 rounded-md border border-line px-3 py-2 text-sm"
        />
        <button type="submit" className="rounded-md bg-accent px-4 py-2 text-sm text-white">
          Send
        </button>
      </form>

      {showFilePicker ? (
        <div className="border-t border-line p-4">
          <p className="mb-2 text-sm font-medium">Share a team document</p>
          <ul className="max-h-40 overflow-y-auto space-y-1 text-sm">
            {teamDocs.data?.documents.map((doc) => (
              <li key={doc.id}>
                <button
                  type="button"
                  onClick={() => shareDocument(doc.id, doc.filename)}
                  className="w-full rounded-md px-2 py-1 text-left hover:bg-surface"
                >
                  {doc.filename}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
