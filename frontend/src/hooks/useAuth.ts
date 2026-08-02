import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, loginUser, registerUser } from '../api/auth'
import { getErrorMessage } from '../api/client'
import { useAuthStore } from '../store/authStore'

export function useCurrentUser(enabled = true) {
  const token = useAuthStore((s) => s.token)
  const setUser = useAuthStore((s) => s.setUser)

  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const user = await fetchMe()
      setUser(user)
      return user
    },
    enabled: enabled && Boolean(token),
    retry: false,
  })
}

export function useLogin() {
  const setAuth = useAuthStore((s) => s.setAuth)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: { email: string; password: string }) => {
      const token = await loginUser(payload)
      useAuthStore.setState({ token: token.access_token })
      const user = await fetchMe()
      setAuth(token.access_token, user)
      return user
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    onError: () => {
      useAuthStore.getState().logout()
    },
    meta: { errorMessage: getErrorMessage },
  })
}

export function useRegister() {
  return useMutation({
    mutationFn: registerUser,
  })
}
