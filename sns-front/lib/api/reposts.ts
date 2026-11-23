import { apiClient } from './client'
import type { RepostCreateRequest, RepostResponse } from '@/lib/types'

export const repostsApi = {
  create: (data: RepostCreateRequest) => {
    return apiClient.post<RepostResponse>('/api/v1/reposts', data)
  },

  delete: (id: number) => {
    return apiClient.delete<void>(`/api/v1/reposts/${id}`)
  },
}
