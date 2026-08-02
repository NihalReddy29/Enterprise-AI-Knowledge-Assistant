import { api } from './client'
import type { TokenResponse, User } from '../types'

export async function registerUser(payload: {
  name: string
  email: string
  password: string
}): Promise<User> {
  const { data } = await api.post<User>('/auth/register', payload)
  return data
}

export async function loginUser(payload: {
  email: string
  password: string
}): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/login', payload)
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me')
  return data
}
