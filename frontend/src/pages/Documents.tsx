import { DocumentUpload } from '../components/DocumentUpload'
import { getErrorMessage } from '../api/client'
import { useDeleteDocument, useDocuments } from '../hooks/useDocuments'
import type { DocumentStatus } from '../types'

const statusStyles: Record<DocumentStatus, string> = {
  pending: 'bg-amber-50 text-warn',
  processing: 'bg-amber-50 text-warn',
  extracted: 'bg-accent-soft text-accent',
  indexed: 'bg-accent-soft text-accent',
  failed: 'bg-red-50 text-danger',
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentsPage() {
  const documents = useDocuments(4000)
  const remove = useDeleteDocument()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl tracking-tight">Documents</h1>
        <p className="mt-2 text-ink-muted">
          Upload and monitor indexing status across your knowledge base.
        </p>
      </div>

      <DocumentUpload />

      <div className="overflow-hidden rounded-xl border border-line bg-panel">
        <div className="border-b border-line px-4 py-3 text-sm font-medium">
          Library ({documents.data?.total ?? 0})
        </div>
        {documents.isLoading ? (
          <p className="px-4 py-8 text-sm text-ink-muted">Loading documents…</p>
        ) : documents.data?.documents.length ? (
          <ul className="divide-y divide-line">
            {documents.data.documents.map((doc) => (
              <li key={doc.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div>
                  <p className="font-medium">{doc.filename}</p>
                  <p className="text-xs text-ink-muted">
                    {doc.file_type.toUpperCase()} · {formatBytes(doc.file_size)}
                    {doc.page_count != null ? ` · ${doc.page_count} pages` : ''}
                    {doc.chunk_count != null ? ` · ${doc.chunk_count} chunks` : ''}
                  </p>
                  {doc.error_message ? (
                    <p className="mt-1 text-xs text-danger">{doc.error_message}</p>
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${statusStyles[doc.status]}`}
                  >
                    {doc.status}
                  </span>
                  <button
                    type="button"
                    className="rounded-md border border-line px-3 py-1.5 text-xs hover:border-danger hover:text-danger"
                    onClick={async () => {
                      if (!confirm(`Delete ${doc.filename}?`)) return
                      try {
                        await remove.mutateAsync(doc.id)
                      } catch (error) {
                        alert(getErrorMessage(error))
                      }
                    }}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-4 py-8 text-sm text-ink-muted">No documents yet. Upload your first file.</p>
        )}
      </div>
    </div>
  )
}
