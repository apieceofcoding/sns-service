import { apiClient } from './client'
import type { LikeCreateRequest, LikeResponse } from '@/lib/types'

export const likesApi = {
  create: (data: LikeCreateRequest) => {
    return apiClient.post<LikeResponse>('/api/v1/likes', data)
  },

  delete: (id: number) => {
    return apiClient.delete<void>(`/api/v1/likes/${id}`)
  },
}
