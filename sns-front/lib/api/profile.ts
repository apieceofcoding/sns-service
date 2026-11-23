import { apiClient } from './client'
import type { Post, MediaInitResponse, ProfileImageInitRequest } from '@/lib/types'

export const profileApi = {
  getMyLikes: () => {
    return apiClient.get<Post[]>('/api/v1/profile/likes')
  },

  initProfileImage: (data: ProfileImageInitRequest) => {
    return apiClient.post<MediaInitResponse>('/api/v1/profile/image/init', data)
  },

  uploadedProfileImage: (mediaId: number) => {
    return apiClient.post<void>('/api/v1/profile/image/uploaded', { mediaId })
  },
}
