'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { followsApi } from '@/lib/api/follows'

export function useFollow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (followeeId: number) => followsApi.follow({ followeeId }),
    onSuccess: (_, followeeId) => {
      queryClient.invalidateQueries({ queryKey: ['follows', 'followees'] })
      queryClient.invalidateQueries({ queryKey: ['users'] })
      queryClient.invalidateQueries({ queryKey: ['follows', 'isFollowing', followeeId] })
      toast.success('팔로우했습니다!')
    },
    onError: () => {
      toast.error('팔로우 실패')
    },
  })
}

export function useUnfollow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (followeeId: number) => followsApi.unfollow({ followeeId }),
    onSuccess: (_, followeeId) => {
      queryClient.invalidateQueries({ queryKey: ['follows', 'followees'] })
      queryClient.invalidateQueries({ queryKey: ['users'] })
      queryClient.invalidateQueries({ queryKey: ['follows', 'isFollowing', followeeId] })
      toast.success('언팔로우했습니다!')
    },
    onError: () => {
      toast.error('언팔로우 실패')
    },
  })
}

export function useIsFollowing(followeeId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['follows', 'isFollowing', followeeId],
    queryFn: () => followsApi.isFollowing(followeeId),
    enabled,
  })
}
