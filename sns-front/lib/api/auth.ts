import { apiClient } from './client'

export const authApi = {
  login: (username: string, password: string) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)

    return apiClient.postForm<void>('/api/v1/login', formData)
  },

  logout: () => {
    return apiClient.post<void>('/api/v1/logout')
  },
}
