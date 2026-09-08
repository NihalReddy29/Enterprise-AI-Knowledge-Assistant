import { useState } from 'react'
import { MarkdownAnswer } from './MarkdownAnswer'
import { submitFeedback } from '../api/chat'
import { getErrorMessage } from '../api/client'
import type { ChatMessage, Citation } from '../types'
import { CitationList } from './CitationList'

interface MessageBubbleProps {
  message: ChatMessage
  onCitationClick?: (citation: Citation) => void
}

export function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [feedback, setFeedback] = useState<'helpful' | 'not_helpful' | null>(null)
  const [pending, setPending] = useState(false)

  async function sendFeedback(rating: 0 | 1) {
    if (pending || feedback) return
    setPending(true)
    try {
      await submitFeedback({ messageId: message.id, rating })
      setFeedback(rating === 1 ? 'helpful' : 'not_helpful')
    } catch (error) {
      alert(getErrorMessage(error))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[min(720px,92%)] rounded-2xl px-4 py-3 ${isUser
            ? 'bg-accent text-white'
            : 'border border-line bg-panel text-ink shadow-[0_10px_30px_rgba(16,35,31,0.04)]'
          }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        ) : (
          <MarkdownAnswer content={message.content} />
        )}
        {!isUser && message.citations?.length ? (
          <CitationList citations={message.citations} onSelect={onCitationClick} />
        ) : null}
        {!isUser ? (
          <div className="mt-3 flex items-center gap-2 border-t border-line pt-2">
            <span className="text-xs text-ink-muted">Was this helpful?</span>
            <button
              type="button"
              disabled={pending || feedback !== null}
              onClick={() => void sendFeedback(1)}
              className={`rounded-md px-2 py-1 text-xs ${feedback === 'helpful'
                  ? 'bg-accent-soft text-accent'
                  : 'border border-line hover:border-accent'
                }`}
            >
              Helpful
            </button>
            <button
              type="button"
              disabled={pending || feedback !== null}
              onClick={() => void sendFeedback(0)}
              className={`rounded-md px-2 py-1 text-xs ${feedback === 'not_helpful'
                  ? 'bg-red-50 text-danger'
                  : 'border border-line hover:border-danger'
                }`}
            >
              Not helpful
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}