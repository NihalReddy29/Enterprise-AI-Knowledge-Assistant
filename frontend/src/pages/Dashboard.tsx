import { Link } from 'react-router-dom'
import { useDocuments } from '../hooks/useDocuments'
import { useConversations } from '../hooks/useChat'
import { useAuthStore } from '../store/authStore'

export function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const documents = useDocuments(5000)
  const conversations = useConversations()

  const indexed =
    documents.data?.documents.filter((doc) => doc.status === 'indexed').length ?? 0
  const totalDocs = documents.data?.total ?? 0
  const totalChats = conversations.data?.total ?? 0

  return (
    <div className="space-y-8">
      <section>
        <h1 className="font-display text-4xl tracking-tight">Welcome, {user?.name?.split(' ')[0]}</h1>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Your knowledge workspace is ready. Upload documents, then ask questions with cited answers.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Stat label="Documents" value={String(totalDocs)} />
        <Stat label="Indexed" value={String(indexed)} />
        <Stat label="Conversations" value={String(totalChats)} />
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <Link
          to="/documents"
          className="rounded-xl border border-line bg-panel p-5 transition hover:border-accent"
        >
          <h2 className="text-lg font-semibold">Manage documents</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Upload PDFs, Word, decks, text, and images for indexing.
          </p>
        </Link>
        <Link
          to="/chat"
          className="rounded-xl border border-line bg-panel p-5 transition hover:border-accent"
        >
          <h2 className="text-lg font-semibold">Open chat</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Ask policy and process questions grounded in your corpus.
          </p>
        </Link>
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel px-5 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted">{label}</p>
      <p className="mt-2 font-display text-4xl">{value}</p>
    </div>
  )
}
