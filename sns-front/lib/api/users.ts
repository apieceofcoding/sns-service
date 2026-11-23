import { apiClient } from './client'

export type FollowListKind = 'followers' | 'following'
import type { User, UserSignupRequest, UserResponse, Post, Reply, FollowCountResponse } from '@/lib/types'

export const usersApi = {
  signup: (data: UserSignupRequest) => {
    return apiClient.post<UserResponse>('/api/v1/users/signup', data)
  },

  getMe: () => {
    return apiClient.get<User>('/api/v1/users/me')
  },

  getById: (userId: number) => {
    return apiClient.get<UserResponse>(`/api/v1/users/${userId}`)
  },

  getPosts: (userId: number) => {
    return apiClient.get<Post[]>(`/api/v1/users/${userId}/posts`)
  },

  getReplies: (userId: number) => {
    return apiClient.get<Reply[]>(`/api/v1/users/${userId}/replies`)
  },

  getFollows: (userId: number, kind: FollowListKind) => {
    return apiClient.get<UserResponse[]>(`/api/v1/users/${userId}/${kind}`)
  },

  getFollowCounts: (userId: number) => {
    return apiClient.get<FollowCountResponse>(`/api/v1/users/${userId}/follow_counts`)
  },
}
