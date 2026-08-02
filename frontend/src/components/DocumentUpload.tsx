import { useState } from 'react'
import { getErrorMessage } from '../api/client'
import { useUploadDocument } from '../hooks/useDocuments'

export function DocumentUpload() {
  const upload = useUploadDocument()
  const [message, setMessage] = useState<string | null>(null)

  return (
    <div className="rounded-xl border border-dashed border-line bg-panel/80 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Upload documents</h2>
          <p className="text-sm text-ink-muted">
            PDF, DOCX, PPTX, TXT, and images. Processing runs in the background.
          </p>
        </div>
        <label className="inline-flex cursor-pointer items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {upload.isPending ? 'Uploading…' : 'Choose file'}
          <input
            type="file"
            className="hidden"
            accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.tiff,.bmp"
            disabled={upload.isPending}
            onChange={async (event) => {
              const file = event.target.files?.[0]
              event.target.value = ''
              if (!file) return
              setMessage(null)
              try {
                const result = await upload.mutateAsync(file)
                setMessage(`${result.document.filename} queued · ${result.document.status}`)
              } catch (error) {
                setMessage(getErrorMessage(error))
              }
            }}
          />
        </label>
      </div>
      {message ? <p className="mt-3 text-sm text-ink-muted">{message}</p> : null}
    </div>
  )
}
