import { apiClient } from './client'
import type { Post, PostCreateRequest } from '@/lib/types'

export const postsApi = {
  getById: (id: number) => {
    return apiClient.get<Post>(`/api/v1/posts/${id}`)
  },

  create: (data: PostCreateRequest) => {
    return apiClient.post<Post>('/api/v1/posts', data)
  },

  delete: (id: number) => {
    return apiClient.delete<void>(`/api/v1/posts/${id}`)
  },

  incrementView: (id: number) => {
    return apiClient.post<void>(`/api/v1/posts/${id}/view`)
  },

  recordAction: (action: "impression" | "click", postId: number) => {
    return apiClient
      .post<void>("/api/v1/recommend/actions", { eventId: crypto.randomUUID(), action, postId })
      .catch(() => undefined)
  },
}
