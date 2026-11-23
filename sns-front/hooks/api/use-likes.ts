'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { likesApi } from '@/lib/api/likes'
import type { Post } from '@/lib/types'

export function useLikePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (postId: number) => likesApi.create({ postId }),
    onMutate: async (postId) => {
      await queryClient.cancelQueries({ queryKey: ['posts'] })
      await queryClient.cancelQueries({ queryKey: ['timeline'] })
      await queryClient.cancelQueries({ queryKey: ['posts', postId] })

      const previousPosts = queryClient.getQueryData(['posts'])
      const previousTimeline = queryClient.getQueryData(['timeline'])
      const previousPost = queryClient.getQueryData(['posts', postId])

      const updatePost = (post: Post) => {
        if (post.id === postId) {
          return {
            ...post,
            likeCount: post.likeCount + 1,
            isLikedByMe: true,
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
      queryClient.setQueryData(['posts', postId], (old: Post | undefined) =>
        old ? { ...old, likeCount: old.likeCount + 1, isLikedByMe: true } : old
      )

      return { previousPosts, previousTimeline, previousPost, postId }
    },
    onSuccess: (data, postId, context) => {
      const updatePostWithLikeId = (post: Post) => {
        if (post.id === postId) {
          return {
            ...post,
            likeIdByMe: data.id,
          }
        }
        return post
      }

      queryClient.setQueryData(['posts'], (old: Post[] | undefined) =>
        old?.map(updatePostWithLikeId)
      )
      queryClient.setQueryData(['timeline'], (old: Post[] | undefined) =>
        old?.map(updatePostWithLikeId)
      )
      queryClient.setQueryData(['posts', postId], (old: Post | undefined) =>
        old ? { ...old, likeIdByMe: data.id } : old
      )
    },
    onError: (_error, postId, context) => {
      if (context?.previousPosts) {
        queryClient.setQueryData(['posts'], context.previousPosts)
      }
      if (context?.previousTimeline) {
        queryClient.setQueryData(['timeline'], context.previousTimeline)
      }
      if (context?.previousPost) {
        queryClient.setQueryData(['posts', postId], context.previousPost)
      }
      toast.error('좋아요 실패')
    },
    onSettled: (data, error, postId) => {
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
      queryClient.invalidateQueries({ queryKey: ['posts', postId] })
      queryClient.invalidateQueries({ queryKey: ['profile', 'likes'] })
    },
  })
}

export function useUnlikePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ likeId }: { postId: number; likeId: number }) => likesApi.delete(likeId),
    onMutate: async ({ postId }: { postId: number; likeId: number }) => {
      await queryClient.cancelQueries({ queryKey: ['posts'] })
      await queryClient.cancelQueries({ queryKey: ['timeline'] })
      await queryClient.cancelQueries({ queryKey: ['posts', postId] })

      const previousPosts = queryClient.getQueryData(['posts'])
      const previousTimeline = queryClient.getQueryData(['timeline'])
      const previousPost = queryClient.getQueryData(['posts', postId])

      const updatePost = (post: Post) => {
        if (post.id === postId) {
          return {
            ...post,
            likeCount: Math.max(0, post.likeCount - 1),
            isLikedByMe: false,
            likeIdByMe: null,
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
      queryClient.setQueryData(['posts', postId], (old: Post | undefined) =>
        old ? { ...old, likeCount: Math.max(0, old.likeCount - 1), isLikedByMe: false, likeIdByMe: null } : old
      )

      return { previousPosts, previousTimeline, previousPost, postId }
    },
    onError: (_error, variables, context) => {
      if (context?.previousPosts) {
        queryClient.setQueryData(['posts'], context.previousPosts)
      }
      if (context?.previousTimeline) {
        queryClient.setQueryData(['timeline'], context.previousTimeline)
      }
      if (context?.previousPost && context?.postId) {
        queryClient.setQueryData(['posts', context.postId], context.previousPost)
      }
      toast.error('좋아요 취소 실패')
    },
    onSettled: (data, error, variables) => {
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
      queryClient.invalidateQueries({ queryKey: ['posts', variables.postId] })
      queryClient.invalidateQueries({ queryKey: ['profile', 'likes'] })
    },
  })
}
