import { create } from 'zustand'

interface ChatUiState {
  activeConversationId: number | null
  setActiveConversationId: (id: number | null) => void
}

export const useChatStore = create<ChatUiState>((set) => ({
  activeConversationId: null,
  setActiveConversationId: (id) => set({ activeConversationId: id }),
}))
