'use client'

import { useQuery } from '@tanstack/react-query'
import { usersApi, type FollowListKind } from '@/lib/api/users'

export function useUser(userId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['users', userId],
    queryFn: () => usersApi.getById(userId),
    enabled,
  })
}

export function useUserPosts(userId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['users', userId, 'posts'],
    queryFn: () => usersApi.getPosts(userId),
    enabled,
  })
}

export function useUserReplies(userId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['users', userId, 'replies'],
    queryFn: () => usersApi.getReplies(userId),
    enabled,
  })
}

export function useUserFollowCounts(userId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['users', userId, 'follow-counts'],
    queryFn: () => usersApi.getFollowCounts(userId),
    enabled,
  })
}

export function useUserFollows(userId: number, kind: FollowListKind) {
  return useQuery({
    queryKey: ['users', userId, kind],
    queryFn: () => usersApi.getFollows(userId, kind),
  })
}
