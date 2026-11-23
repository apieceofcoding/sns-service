import { apiClient } from './client'
import type { Reply, ReplyCreateRequest } from '@/lib/types'

export const repliesApi = {
  create: (postId: number, data: ReplyCreateRequest) => {
    return apiClient.post<Reply>(`/api/v1/posts/${postId}/replies`, data)
  },

  getByPost: (postId: number) => {
    return apiClient.get<Reply[]>(`/api/v1/posts/${postId}/replies`)
  },
}
