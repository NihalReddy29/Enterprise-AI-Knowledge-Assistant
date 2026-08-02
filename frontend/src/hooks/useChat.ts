import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  askQuestion,
  deleteConversation,
  getConversation,
  listConversations,
} from '../api/chat'

export function useConversations() {
  return useQuery({
    queryKey: ['conversations'],
    queryFn: listConversations,
  })
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: ['conversation', id],
    queryFn: () => getConversation(id!),
    enabled: id != null,
  })
}

export function useAskQuestion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: askQuestion,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({ queryKey: ['conversation', data.conversation_id] })
    },
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })
}
