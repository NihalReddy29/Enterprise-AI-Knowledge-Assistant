import { useEffect, useMemo, useRef, useState } from 'react'
import { getDocument, fetchDocumentFile, fetchDocumentHighlight } from '../api/documents'
import { getErrorMessage } from '../api/client'
import type { Citation, DocumentHighlight, DocumentItem } from '../types'

interface DocumentViewerProps {
  citation: Citation
  onClose: () => void
}

function highlightPageText(pageText: string, matches: DocumentHighlight['matches']): string {
  if (!matches.length) return pageText
  const ordered = [...matches].sort((a, b) => a.start - b.start)
  let cursor = 0
  let html = ''
  for (const match of ordered) {
    if (match.start < cursor) continue
    html += escapeHtml(pageText.slice(cursor, match.start))
    html += `<mark class="source-hl">${escapeHtml(pageText.slice(match.start, match.end))}</mark>`
    cursor = match.end
  }
  html += escapeHtml(pageText.slice(cursor))
  return html
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

export function DocumentViewer({ citation, onClose }: DocumentViewerProps) {
  const [doc, setDoc] = useState<DocumentItem | null>(null)
  const [highlight, setHighlight] = useState<DocumentHighlight | null>(null)
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const objectUrlRef = useRef<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [meta, hl, blob] = await Promise.all([
          getDocument(citation.document_id),
          fetchDocumentHighlight({
            documentId: citation.document_id,
            excerpt: citation.text || citation.document || ' ',
            pageNumber: citation.page_number,
            section: citation.section,
          }),
          fetchDocumentFile(citation.document_id),
        ])
        if (cancelled) return

        if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
        const url = URL.createObjectURL(blob)
        objectUrlRef.current = url
        setDoc(meta)
        setHighlight(hl)
        setFileUrl(url)
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = null
      }
    }
  }, [citation])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const highlightedHtml = useMemo(() => {
    if (!highlight) return ''
    return highlightPageText(highlight.page_text, highlight.matches)
  }, [highlight])

  const pageNumber = highlight?.page_number ?? citation.page_number ?? 1
  const isPdf = (doc?.file_type || highlight?.file_type || '').toLowerCase() === 'pdf'
  const isImage = ['png', 'jpg', 'jpeg', 'tiff', 'bmp'].includes(
    (doc?.file_type || '').toLowerCase(),
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/55 p-4 backdrop-blur-[2px]">
      <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-panel shadow-[0_40px_100px_rgba(16,35,31,0.35)]">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Source viewer
            </p>
            <h2 className="mt-1 text-lg font-semibold">
              {doc?.filename || citation.document || `Document #${citation.document_id}`}
            </h2>
            <p className="text-sm text-ink-muted">
              Page {pageNumber}
              {highlight?.section ? ` · ${highlight.section}` : ''}
              {highlight?.matches.length
                ? ` · ${highlight.matches.length} highlight${highlight.matches.length > 1 ? 's' : ''}`
                : ' · excerpt preview'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-line px-3 py-1.5 text-sm hover:border-accent"
          >
            Close
          </button>
        </header>

        <div className="grid min-h-0 flex-1 gap-0 overflow-hidden lg:grid-cols-[1.2fr_0.8fr]">
          <div className="min-h-[320px] overflow-auto border-b border-line bg-surface p-4 lg:border-b-0 lg:border-r">
            {loading ? (
              <p className="text-sm text-ink-muted">Loading source…</p>
            ) : error ? (
              <p className="text-sm text-danger">{error}</p>
            ) : isPdf && fileUrl ? (
              <PdfPageCanvas fileUrl={fileUrl} pageNumber={pageNumber} searchText={citation.text} />
            ) : isImage && fileUrl ? (
              <img
                src={fileUrl}
                alt={doc?.filename || 'Document image'}
                className="mx-auto max-h-[70vh] rounded-md border border-line object-contain"
              />
            ) : (
              <div className="rounded-md border border-line bg-panel p-4 text-sm leading-relaxed whitespace-pre-wrap">
                <div dangerouslySetInnerHTML={{ __html: highlightedHtml || escapeHtml(citation.text) }} />
              </div>
            )}
          </div>

          <aside className="overflow-auto p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Matching paragraph
            </p>
            <div
              className="mt-3 rounded-md border border-line bg-surface p-3 text-sm leading-relaxed whitespace-pre-wrap"
              dangerouslySetInnerHTML={{
                __html: highlightedHtml || escapeHtml(citation.text || 'No excerpt available.'),
              }}
            />
            <p className="mt-4 text-xs text-ink-muted">
              Citation score {citation.similarity_score.toFixed(3)}. Highlighted spans are matched
              against extracted page text.
            </p>
          </aside>
        </div>
      </div>

      <style>{`
        mark.source-hl {
          background: #fef08a;
          color: inherit;
          padding: 0 0.1em;
          border-radius: 0.15em;
        }
      `}</style>
    </div>
  )
}

interface PdfPageCanvasProps {
  fileUrl: string
  pageNumber: number
  searchText: string
}

function PdfPageCanvas({ fileUrl, pageNumber, searchText }: PdfPageCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const textLayerRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState('Rendering PDF page…')

  useEffect(() => {
    let cancelled = false

    async function render() {
      try {
        const pdfjs = await import('pdfjs-dist')
        const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url')
        pdfjs.GlobalWorkerOptions.workerSrc = worker.default

        const loadingTask = pdfjs.getDocument({ url: fileUrl })
        const pdf = await loadingTask.promise
        const page = await pdf.getPage(Math.min(Math.max(pageNumber, 1), pdf.numPages))
        const viewport = page.getViewport({ scale: 1.35 })

        const canvas = canvasRef.current
        const textLayerDiv = textLayerRef.current
        if (!canvas || !textLayerDiv || cancelled) return

        const context = canvas.getContext('2d')
        if (!context) return

        canvas.height = viewport.height
        canvas.width = viewport.width
        textLayerDiv.style.width = `${viewport.width}px`
        textLayerDiv.style.height = `${viewport.height}px`
        textLayerDiv.innerHTML = ''

        await page.render({
          canvasContext: context,
          viewport,
          canvas,
        }).promise

        const textContent = await page.getTextContent()
        const needle = normalize(searchText).slice(0, 120)
        const frag = document.createDocumentFragment()

        for (const item of textContent.items) {
          if (!('str' in item) || !item.str) continue
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const util = (pdfjs as any).Util
          const tx = util.transform(viewport.transform, item.transform)
          const fontHeight = Math.hypot(tx[2], tx[3])
          const span = document.createElement('span')
          span.textContent = item.str
          span.style.left = `${tx[4]}px`
          span.style.top = `${tx[5] - fontHeight}px`
          span.style.fontSize = `${fontHeight}px`
          span.style.fontFamily = 'sans-serif'
          span.style.position = 'absolute'
          span.style.whiteSpace = 'pre'
          span.style.color = 'transparent'
          span.style.transformOrigin = '0% 0%'

          const itemNorm = normalize(item.str)
          const shortNeedle = needle.slice(0, Math.min(24, needle.length))
          if (shortNeedle && itemNorm.includes(shortNeedle)) {
            span.className = 'pdf-hl'
          } else if (
            needle &&
            needle.split(' ').some((token) => token.length > 4 && itemNorm.includes(token))
          ) {
            span.className = 'pdf-hl'
          }

          frag.appendChild(span)
        }

        if (!cancelled) {
          textLayerDiv.appendChild(frag)
          setStatus('')
        }
      } catch (err) {
        if (!cancelled) setStatus(getErrorMessage(err))
      }
    }

    void render()
    return () => {
      cancelled = true
    }
  }, [fileUrl, pageNumber, searchText])

  return (
    <div className="space-y-3">
      {status ? <p className="text-sm text-ink-muted">{status}</p> : null}
      <div className="relative inline-block max-w-full overflow-auto rounded-md border border-line bg-white">
        <canvas ref={canvasRef} className="block max-w-full" />
        <div ref={textLayerRef} className="pointer-events-none absolute left-0 top-0" />
      </div>
      <style>{`
        .pdf-hl {
          background: rgba(250, 204, 21, 0.45) !important;
          color: transparent !important;
          border-radius: 2px;
        }
      `}</style>
    </div>
  )
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/\s+/g, ' ').trim()
}
