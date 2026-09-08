import { useState } from 'react'
import { getErrorMessage } from '../api/client'
import { DocumentUpload } from '../components/DocumentUpload'
import { useDeleteDocument, useDocuments } from '../hooks/useDocuments'
import { useOrgs, usePublishDocument, useUnpublishDocument } from '../hooks/useOrgs'
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
  const orgs = useOrgs()
  const publish = usePublishDocument()
  const unpublish = useUnpublishDocument()

  const [publishingDocId, setPublishingDocId] = useState<number | null>(null)
  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null)

  async function handlePublish(docId: number) {
    if (!selectedOrgId) return
    try {
      await publish.mutateAsync({ documentId: docId, orgId: selectedOrgId })
      setPublishingDocId(null)
    } catch (err) {
      alert(getErrorMessage(err))
    }
  }

  async function handleUnpublish(docId: number) {
    try {
      await unpublish.mutateAsync(docId)
    } catch (err) {
      alert(getErrorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl tracking-tight">Documents</h1>
        <p className="mt-2 text-ink-muted">
          Upload and monitor indexing status across your knowledge base and shared team libraries.
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
            {documents.data.documents.map((doc) => {
              const matchedOrg = orgs.data?.find((o) => o.id === doc.org_id)
              return (
                <li key={doc.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{doc.filename}</p>
                      {doc.org_id ? (
                        <span className="rounded-full bg-purple-50 px-2 py-0.5 text-[11px] font-semibold text-purple-700">
                          {matchedOrg ? matchedOrg.name : `Org #${doc.org_id}`}
                        </span>
                      ) : null}
                    </div>
                    <p className="text-xs text-ink-muted">
                      {doc.file_type.toUpperCase()} · {formatBytes(doc.file_size)}
                      {doc.page_count != null ? ` · ${doc.page_count} pages` : ''}
                      {doc.chunk_count != null ? ` · ${doc.chunk_count} chunks` : ''}
                    </p>
                    {doc.error_message ? (
                      <p className="mt-1 text-xs text-danger">{doc.error_message}</p>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${statusStyles[doc.status]}`}
                    >
                      {doc.status}
                    </span>

                    {/* Org publish/unpublish action */}
                    {orgs.data?.length ? (
                      doc.org_id ? (
                        <button
                          type="button"
                          disabled={unpublish.isPending}
                          onClick={() => handleUnpublish(doc.id)}
                          className="rounded-md border border-line px-2.5 py-1 text-xs font-medium text-ink-muted hover:bg-surface hover:text-ink"
                        >
                          Unpublish
                        </button>
                      ) : publishingDocId === doc.id ? (
                        <div className="flex items-center gap-1">
                          <select
                            value={selectedOrgId || ''}
                            onChange={(e) => setSelectedOrgId(Number(e.target.value))}
                            className="rounded-md border border-line bg-surface px-2 py-1 text-xs outline-none"
                          >
                            <option value="">Select Team</option>
                            {orgs.data.map((o) => (
                              <option key={o.id} value={o.id}>
                                {o.name}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            disabled={!selectedOrgId || publish.isPending}
                            onClick={() => handlePublish(doc.id)}
                            className="rounded-md bg-accent px-2 py-1 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            onClick={() => setPublishingDocId(null)}
                            className="text-xs text-ink-muted hover:underline"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setPublishingDocId(doc.id)
                            setSelectedOrgId(orgs.data[0]?.id || null)
                          }}
                          className="rounded-md border border-line px-2.5 py-1 text-xs font-medium text-accent hover:bg-accent-soft"
                        >
                          Publish to Team
                        </button>
                      )
                    ) : null}

                    <button
                      type="button"
                      className="rounded-md border border-line px-3 py-1 text-xs hover:border-danger hover:text-danger"
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
              )
            })}
          </ul>
        ) : (
          <p className="px-4 py-8 text-sm text-ink-muted">No documents yet. Upload your first file.</p>
        )}
      </div>
    </div>
  )
}
