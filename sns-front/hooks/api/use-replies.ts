'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { repliesApi } from '@/lib/api/replies'
import type { Post, ReplyCreateRequest } from '@/lib/types'

export function useReplies(postId: number | null) {
  return useQuery({
    queryKey: ['replies', postId],
    queryFn: () => repliesApi.getByPost(postId!),
    enabled: !!postId,
  })
}

export function useCreateReply() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ postId, data }: { postId: number; data: ReplyCreateRequest }) =>
      repliesApi.create(postId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['replies', variables.postId] })
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
      queryClient.setQueryData(['posts', variables.postId], (old: Post | undefined) => {
        if (old) {
          return { ...old, replyCount: old.replyCount + 1 }
        }
        return old
      })
      toast.success('답글이 작성되었습니다!')
    },
    onError: () => {
      toast.error('답글 작성 실패')
    },
  })
}
