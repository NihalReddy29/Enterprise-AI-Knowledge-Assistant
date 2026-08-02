import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'
import { useState } from 'react'
import {
  deleteUser,
  getStatistics,
  getStorageStats,
  listAdminDocuments,
  listAdminFeedback,
  listAdminQueries,
  listUsers,
} from '../api/admin'
import { getErrorMessage } from '../api/client'
import { useAuthStore } from '../store/authStore'

type AdminTab = 'overview' | 'users' | 'documents' | 'queries' | 'feedback'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function AdminPage() {
  const user = useAuthStore((s) => s.user)
  const [tab, setTab] = useState<AdminTab>('overview')
  const queryClient = useQueryClient()

  const enabled = user?.role === 'admin'
  const stats = useQuery({ queryKey: ['admin-stats'], queryFn: getStatistics, enabled })
  const users = useQuery({ queryKey: ['admin-users'], queryFn: listUsers, enabled })
  const documents = useQuery({
    queryKey: ['admin-documents'],
    queryFn: listAdminDocuments,
    enabled: enabled && (tab === 'documents' || tab === 'overview'),
  })
  const storage = useQuery({
    queryKey: ['admin-storage'],
    queryFn: getStorageStats,
    enabled: enabled && (tab === 'documents' || tab === 'overview'),
  })
  const queries = useQuery({
    queryKey: ['admin-queries'],
    queryFn: listAdminQueries,
    enabled: enabled && (tab === 'queries' || tab === 'overview'),
  })
  const feedback = useQuery({
    queryKey: ['admin-feedback'],
    queryFn: listAdminFeedback,
    enabled: enabled && (tab === 'feedback' || tab === 'overview'),
  })

  const removeUser = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
    },
  })

  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  const tabs: { id: AdminTab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'users', label: 'Users' },
    { id: 'documents', label: 'Documents' },
    { id: 'queries', label: 'Queries' },
    { id: 'feedback', label: 'Feedback' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl tracking-tight">Admin</h1>
        <p className="mt-2 text-ink-muted">
          Monitor users, storage, queries, and answer quality across the platform.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${
              tab === item.id ? 'bg-accent text-white' : 'bg-panel text-ink-muted border border-line'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Users" value={stats.data?.total_users ?? '—'} />
            <Metric label="Documents" value={stats.data?.total_documents ?? '—'} />
            <Metric label="Questions" value={stats.data?.total_questions ?? '—'} />
            <Metric label="Storage" value={stats.data ? `${stats.data.storage_mb} MB` : '—'} />
          </section>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Indexed" value={stats.data?.indexed_documents ?? '—'} />
            <Metric label="Failed docs" value={stats.data?.failed_documents ?? '—'} />
            <Metric label="Helpful" value={stats.data?.helpful_feedback ?? '—'} />
            <Metric label="Not helpful" value={stats.data?.not_helpful_feedback ?? '—'} />
          </section>

          <section className="rounded-xl border border-line bg-panel p-5">
            <h2 className="text-lg font-semibold">Most searched topics</h2>
            {stats.data?.most_searched_topics?.length ? (
              <ul className="mt-3 space-y-2">
                {stats.data.most_searched_topics.map((topic) => (
                  <li
                    key={topic.topic}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="capitalize">{topic.topic}</span>
                    <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">
                      {topic.count}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-ink-muted">No queries logged yet.</p>
            )}
          </section>
        </div>
      ) : null}

      {tab === 'users' ? (
        <section className="overflow-hidden rounded-xl border border-line bg-panel">
          <div className="border-b border-line px-4 py-3 text-sm font-medium">
            Users ({users.data?.total ?? 0})
          </div>
          <ul className="divide-y divide-line">
            {users.data?.users.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                <div>
                  <p className="font-medium">{item.name}</p>
                  <p className="text-ink-muted">{item.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold capitalize text-accent">
                    {item.role}
                  </span>
                  {item.id !== user?.id ? (
                    <button
                      type="button"
                      className="rounded-md border border-line px-3 py-1.5 text-xs hover:border-danger hover:text-danger"
                      onClick={async () => {
                        if (!confirm(`Delete ${item.email}?`)) return
                        try {
                          await removeUser.mutateAsync(item.id)
                        } catch (error) {
                          alert(getErrorMessage(error))
                        }
                      }}
                    >
                      Delete
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {tab === 'documents' ? (
        <div className="space-y-4">
          <section className="grid gap-4 sm:grid-cols-3">
            <Metric label="Files" value={storage.data?.total_documents ?? '—'} />
            <Metric label="Total size" value={storage.data ? formatBytes(storage.data.total_bytes) : '—'} />
            <Metric
              label="Types"
              value={storage.data?.by_type?.length ?? '—'}
            />
          </section>
          {storage.data?.by_type?.length ? (
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="text-sm font-semibold">Storage by type</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {storage.data.by_type.map((row) => (
                  <li key={row.file_type} className="flex justify-between">
                    <span className="uppercase">{row.file_type}</span>
                    <span className="text-ink-muted">
                      {row.count} · {formatBytes(row.total_bytes)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <section className="overflow-hidden rounded-xl border border-line bg-panel">
            <div className="border-b border-line px-4 py-3 text-sm font-medium">
              All documents ({documents.data?.total ?? 0})
            </div>
            <ul className="divide-y divide-line">
              {documents.data?.documents.map((doc) => (
                <li key={doc.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                  <div>
                    <p className="font-medium">{doc.filename}</p>
                    <p className="text-xs text-ink-muted">
                      Owner #{doc.owner_id} · {doc.file_type.toUpperCase()} · {formatBytes(doc.file_size)}
                    </p>
                  </div>
                  <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold capitalize text-accent">
                    {doc.status}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}

      {tab === 'queries' ? (
        <section className="overflow-hidden rounded-xl border border-line bg-panel">
          <div className="border-b border-line px-4 py-3 text-sm font-medium">
            Recent queries ({queries.data?.total ?? 0})
          </div>
          <ul className="divide-y divide-line">
            {queries.data?.queries.map((item) => (
              <li key={item.id} className="px-4 py-3 text-sm">
                <p className="font-medium">{item.question}</p>
                <p className="mt-1 text-xs text-ink-muted">
                  {item.user_name || item.user_email || `User #${item.user_id}`}
                  {item.topic ? ` · topic: ${item.topic}` : ''}
                  {` · ${item.citation_count} citations`}
                  {item.insufficient_information ? ' · insufficient info' : ''}
                </p>
              </li>
            ))}
            {!queries.data?.queries.length ? (
              <li className="px-4 py-6 text-sm text-ink-muted">No queries yet.</li>
            ) : null}
          </ul>
        </section>
      ) : null}

      {tab === 'feedback' ? (
        <section className="overflow-hidden rounded-xl border border-line bg-panel">
          <div className="border-b border-line px-4 py-3 text-sm font-medium">
            Feedback ({feedback.data?.total ?? 0})
          </div>
          <ul className="divide-y divide-line">
            {feedback.data?.feedback.map((item) => (
              <li key={item.id} className="px-4 py-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">
                    {item.rating === 1 ? 'Helpful' : 'Not helpful'}
                  </p>
                  <span className="text-xs text-ink-muted">{item.user_email}</span>
                </div>
                {item.comment ? <p className="mt-1 text-ink-muted">{item.comment}</p> : null}
                {item.message_content ? (
                  <p className="mt-2 rounded-md bg-surface p-2 text-xs text-ink">
                    {item.message_content}
                  </p>
                ) : null}
              </li>
            ))}
            {!feedback.data?.feedback.length ? (
              <li className="px-4 py-6 text-sm text-ink-muted">No feedback submitted yet.</li>
            ) : null}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-line bg-panel px-5 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted">{label}</p>
      <p className="mt-2 font-display text-4xl">{value}</p>
    </div>
  )
}
