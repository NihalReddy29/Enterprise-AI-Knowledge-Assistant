import { useCallback, useRef, useState } from 'react'
import { getErrorMessage } from '../api/client'
import { useUploadDocument } from '../hooks/useDocuments'
import { useUploadTeamDocument } from '../hooks/useTeams'

interface DocumentUploadProps {
  teamId?: number | null
}

const ACCEPTED_EXTENSIONS = new Set([
  '.pdf',
  '.docx',
  '.pptx',
  '.txt',
  '.png',
  '.jpg',
  '.jpeg',
  '.tiff',
  '.bmp',
])

const ACCEPT_ATTR = '.pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.tiff,.bmp'

function isAcceptedFile(file: File): boolean {
  const dot = file.name.lastIndexOf('.')
  if (dot === -1) return false
  return ACCEPTED_EXTENSIONS.has(file.name.slice(dot).toLowerCase())
}

export function DocumentUpload({ teamId }: DocumentUploadProps) {
  const uploadPersonal = useUploadDocument()
  const uploadTeam = useUploadTeamDocument()
  const isUploading = teamId ? uploadTeam.isPending : uploadPersonal.isPending
  const [message, setMessage] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const dragCounter = useRef(0)

  const uploadFiles = useCallback(
    async (files: FileList | File[]) => {
      const accepted = Array.from(files).filter(isAcceptedFile)
      if (!accepted.length) {
        setMessage('No supported files found. Use PDF, DOCX, PPTX, TXT, or images.')
        return
      }

      setMessage(null)
      const queued: string[] = []
      const errors: string[] = []

      for (const file of accepted) {
        try {
          const result = teamId
            ? await uploadTeam.mutateAsync({ teamId, file })
            : await uploadPersonal.mutateAsync(file)
          queued.push(result.document.filename)
        } catch (error) {
          errors.push(`${file.name}: ${getErrorMessage(error)}`)
        }
      }

      if (queued.length) {
        const summary =
          queued.length === 1
            ? `${queued[0]} queued`
            : `${queued.length} files queued (${queued.join(', ')})`
        setMessage(errors.length ? `${summary}. Failed: ${errors.join('; ')}` : summary)
      } else if (errors.length) {
        setMessage(errors.join('; '))
      }
    },
    [teamId, uploadPersonal, uploadTeam],
  )

  const onDragEnter = (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    dragCounter.current += 1
    if (event.dataTransfer.types.includes('Files')) {
      setIsDragging(true)
    }
  }

  const onDragLeave = (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    dragCounter.current -= 1
    if (dragCounter.current <= 0) {
      dragCounter.current = 0
      setIsDragging(false)
    }
  }

  const onDragOver = (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    event.dataTransfer.dropEffect = isUploading ? 'none' : 'copy'
  }

  const onDrop = async (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()
    dragCounter.current = 0
    setIsDragging(false)
    if (isUploading || !event.dataTransfer.files.length) return
    await uploadFiles(event.dataTransfer.files)
  }

  const zoneClass = [
    'rounded-xl border border-dashed p-5 transition-colors',
    isDragging ? 'border-accent bg-accent-soft/40' : 'border-line bg-panel/80',
    isUploading ? 'pointer-events-none opacity-60' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={zoneClass}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Upload documents</h2>
          <p className="text-sm text-ink-muted">
            {isDragging
              ? 'Release to upload your files'
              : 'Drag and drop files here, or choose from your computer. PDF, DOCX, PPTX, TXT, and images.'}
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {isUploading ? 'Uploading…' : 'Choose files'}
          <input
            type="file"
            className="hidden"
            accept={ACCEPT_ATTR}
            multiple
            disabled={isUploading}
            onChange={async (event) => {
              const files = event.target.files
              event.target.value = ''
              if (!files?.length) return
              await uploadFiles(files)
            }}
          />
        </label>
      </div>
      {message ? <p className="mt-3 text-sm text-ink-muted">{message}</p> : null}
    </div>
  )
}
