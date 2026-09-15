import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteDocument, listDocuments, uploadDocument } from '../api/documents'

export function useDocuments(refetchInterval?: number | false, enabled = true) {
  return useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
    refetchInterval,
    enabled,
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}
