import { apiClient } from './client'
import type { Post, Reply, MediaInitResponse, ProfileImageInitRequest } from '@/lib/types'

export const profileApi = {
  getMyPosts: () => {
    return apiClient.get<Post[]>('/api/v1/profile/posts')
  },

  getMyReplies: () => {
    return apiClient.get<Reply[]>('/api/v1/profile/replies')
  },

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
