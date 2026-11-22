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
    onError: (error) => {
      toast.error('답글 작성 실패')
      console.error('Create reply error:', error)
    },
  })
}

export function useDeleteReply() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ replyId, postId }: { replyId: number; postId: number }) =>
      repliesApi.delete(replyId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['replies', variables.postId] })
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
      toast.success('답글이 삭제되었습니다!')
    },
    onError: (error) => {
      toast.error('답글 삭제 실패')
      console.error('Delete reply error:', error)
    },
  })
}
