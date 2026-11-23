import { apiClient } from './client'
import type { FollowRequest, FollowResponse } from '@/lib/types'

export const followsApi = {
  follow: (data: FollowRequest) => {
    return apiClient.post<FollowResponse>('/api/v1/follows', data)
  },

  unfollow: (data: FollowRequest) => {
    return apiClient.delete<void>('/api/v1/follows', { body: JSON.stringify(data) })
  },

  isFollowing: (followeeId: number) => {
    return apiClient.get<boolean>(`/api/v1/follows/check/${followeeId}`)
  },
}
