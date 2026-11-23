'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { repostsApi } from '@/lib/api/reposts'
import type { Post } from '@/lib/types'

export function useRepost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (postId: number) => repostsApi.create({ postId }),
    onMutate: async (postId) => {
      await queryClient.cancelQueries({ queryKey: ['posts'] })
      await queryClient.cancelQueries({ queryKey: ['timeline'] })

      const previousPosts = queryClient.getQueryData(['posts'])
      const previousTimeline = queryClient.getQueryData(['timeline'])

      const updatePost = (post: Post) => {
        if (post.id === postId) {
          return {
            ...post,
            repostCount: post.repostCount + 1,
            isRepostedByMe: true,
          }
        }
        return post
      }

      queryClient.setQueryData(['posts'], (old: Post[] | undefined) =>
        old?.map(updatePost)
      )
      queryClient.setQueryData(['timeline'], (old: Post[] | undefined) =>
        old?.map(updatePost)
      )

      return { previousPosts, previousTimeline }
    },
    onError: (_error, postId, context) => {
      if (context?.previousPosts) {
        queryClient.setQueryData(['posts'], context.previousPosts)
      }
      if (context?.previousTimeline) {
        queryClient.setQueryData(['timeline'], context.previousTimeline)
      }
      toast.error('리포스트 실패')
    },
    onSuccess: () => {
      toast.success('리포스트했습니다!')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
    },
  })
}

export function useUnrepost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ repostId }: { postId: number; repostId: number }) => repostsApi.delete(repostId),
    onMutate: async ({ postId }) => {
      await queryClient.cancelQueries({ queryKey: ['posts'] })
      await queryClient.cancelQueries({ queryKey: ['timeline'] })

      const previousPosts = queryClient.getQueryData(['posts'])
      const previousTimeline = queryClient.getQueryData(['timeline'])

      const updatePost = (post: Post) => {
        if (post.id === postId) {
          return {
            ...post,
            repostCount: Math.max(0, post.repostCount - 1),
            isRepostedByMe: false,
          }
        }
        return post
      }

      queryClient.setQueryData(['posts'], (old: Post[] | undefined) =>
        old?.map(updatePost)
      )
      queryClient.setQueryData(['timeline'], (old: Post[] | undefined) =>
        old?.map(updatePost)
      )

      return { previousPosts, previousTimeline }
    },
    onError: (_error, variables, context) => {
      if (context?.previousPosts) {
        queryClient.setQueryData(['posts'], context.previousPosts)
      }
      if (context?.previousTimeline) {
        queryClient.setQueryData(['timeline'], context.previousTimeline)
      }
      toast.error('리포스트 취소 실패')
    },
    onSuccess: () => {
      toast.success('리포스트를 취소했습니다!')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
    },
  })
}
