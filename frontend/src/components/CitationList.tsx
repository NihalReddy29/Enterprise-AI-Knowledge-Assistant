import type { Citation } from '../types'

interface CitationListProps {
  citations: Citation[]
  onSelect?: (citation: Citation) => void
}

export function CitationList({ citations, onSelect }: CitationListProps) {
  if (!citations.length) return null

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted">
        Sources
      </p>
      <ol className="space-y-2">
        {citations.map((citation) => (
          <li key={`${citation.document_id}-${citation.index}`}>
            <button
              type="button"
              onClick={() => onSelect?.(citation)}
              className="w-full rounded-md border border-line bg-panel px-3 py-2 text-left transition hover:border-accent hover:bg-accent-soft"
            >
              <p className="text-sm font-medium text-ink">
                {citation.index}. {citation.document || `Document #${citation.document_id}`}
              </p>
              <p className="mt-0.5 text-xs text-ink-muted">
                {citation.page_number != null ? `Page ${citation.page_number}` : 'Page n/a'}
                {citation.section ? ` · ${citation.section}` : ''}
                {` · score ${citation.similarity_score.toFixed(2)}`}
              </p>
            </button>
          </li>
        ))}
      </ol>
    </div>
  )
}
